# ADR 0002 · Observabilidad y versionado

- **Estado**: aceptado
- **Fecha**: 2026-11-21

## Contexto

Hace falta ver cómo responde el sistema, saber si funciona bien o mal y seguir cómo cambia su comportamiento a medida que crece la base de conocimiento. En esta aplicación no se entrena ningún modelo, pero su comportamiento depende de cinco piezas que cambian con el tiempo:

- El código del grafo.
- El modelo base de cada rol.
- Los prompts.
- La configuración de recuperación, como el chunker, el top-k o el reranker.
- La base de conocimiento indexada.

Si una métrica empeora, hay que poder saber cuál de esas piezas cambió. Por eso el versionado sí aplica aquí, aunque lo que se versiona es distinto que en ML clásico.

## Equivalencias con MLOps clásico

| ML clásico | Esta aplicación con RAG |
|---|---|
| Dataset de entrenamiento versionado | Base de conocimiento y su índice versionados |
| Pesos del modelo | Modelo base, prompts y configuración de recuperación |
| Model registry | Registro de prompts y de configuración por versión |
| Métricas de validación | Evals por rol del laboratorio de modelos |
| Monitoreo de drift | Cambios en las preguntas de los usuarios y en la base |

## Decisión

### 1. Huella de versión en cada traza

Cada petición registra en su traza de Langfuse:

- **app_version**: tag semver y commit de git.
- **model**: proveedor, modelo y cuantización de cada rol.
- **prompt_version**: versión de cada prompt usado.
- **index_version**: versión del índice que respondió.
- **retrieval_config**: chunker, top-k y reranker.

Así cualquier gráfica se puede filtrar o comparar por versión, y un cambio en una métrica se atribuye a una pieza concreta.

### 2. Versionado de la base de conocimiento

- **Documentos fuente en git**, en la carpeta `knowledge/`. Son textos pequeños, y para ese tamaño git ya es versionado de datos.
- **Manifiesto de ingesta en Postgres**: cada ingesta crea un `index_version` y registra por documento su hash de contenido, la versión del chunker, el modelo de embeddings y la fecha.
- **Ingesta incremental**: solo se reprocesan los documentos cuyo hash cambió.
- **Versiones anteriores conservadas**: una versión del índice se marca como activa y las anteriores quedan disponibles para comparar o volver atrás.
- **Eval de regresión tras cada ingesta**: el eval de recuperación corre contra la versión nueva y la anterior. Agregar documentos puede empeorar la búsqueda, ya que cada documento nuevo también es un posible distractor.
- **DVC 3.67** queda para cuando los documentos sean grandes o binarios, como PDF escaneados, porque ahí git deja de servir.

### 3. Prompts y datasets versionados

- Los prompts empiezan como archivos en git y en F5 pasan al prompt management de Langfuse, con etiquetas `staging` y `production`. El código pide la etiqueta y cada traza guarda la versión exacta que usó.
- Los datasets de evaluación se versionan en Langfuse, de modo que cada experimento sabe contra qué versión del dataset corrió.

### 4. Tres niveles de observabilidad

| Nivel | Pregunta que responde | Herramienta |
|---|---|---|
| Trazas | ¿Qué pasó en esta conversación? Nodos, llamadas al LLM, tools, chunks recuperados con su puntuación, latencia y tokens | Langfuse |
| Producto y calidad | ¿Cómo evoluciona el sistema en el tiempo? | Dashboards de Langfuse |
| Sistema | ¿Aguanta la infraestructura? Latencia y errores del API, Postgres, uso de GPU y VRAM | Prometheus y Grafana, como en mlops-housing-api |

Métricas que se siguen:

- **Calidad**: rechazos del auditor, escalados a un humano, citas confirmadas frente a abandonadas, feedback del usuario y fidelidad estimada por un juez local sobre una muestra de conversaciones.
- **Recuperación**: puntuación del mejor chunk, porcentaje de preguntas sin ningún chunk relevante y documentos más y menos citados.
- **Fiabilidad**: JSON inválido, reintentos, timeouts y errores de tools.
- **Rendimiento**: latencia p50 y p95 por nodo, tiempo hasta el primer token y tokens por segundo.

### 5. Ciclo de mejora continua

1. Producción genera trazas.
2. Un juez local evalúa una muestra y el usuario deja su feedback.
3. Las conversaciones con mala nota pasan a una cola de anotación para revisarlas a mano.
4. Los casos revisados se agregan al dataset dorado.
5. El siguiente cambio de prompt, modelo o índice se mide contra ese dataset ampliado.

Las preguntas que la base no puede responder señalan qué contenido falta agregar.

### 6. Detección de temas nuevos

Agrupar los embeddings de las preguntas de los usuarios permite descubrir temas que la base no cubre. Es una técnica avanzada y queda para F7.

## Sobre MLflow

MLflow 3.18 ya incluye trazas, evaluación y registro de prompts para aplicaciones con LLM, así que también serviría en este proyecto. Se elige Langfuse porque su interfaz está pensada para conversaciones y su versión autoalojada incluye todas las funciones, mientras que usar ambos duplicaría las trazas. MLflow entra en el proyecto 02, donde hay un modelo entrenado cuyos pesos se versionan en su model registry.

## Implementación por fases

| Fase | Qué se añade |
|---|---|
| F0 | request_id y huella de versión en los logs |
| F1 | Langfuse con las trazas del grafo |
| F2 | Manifiesto de ingesta, versiones del índice y eval de regresión tras cada ingesta |
| F5 | Dashboards, juez sobre muestras, feedback, cola de anotación y prompts en Langfuse |
| F7 | Prometheus y Grafana para sistema y GPU, y detección de temas nuevos |

## Consecuencias

- **A favor**: cualquier cambio en una métrica se puede atribuir a una pieza concreta, y la base puede crecer con tranquilidad porque una regresión se detecta en el momento de la ingesta.
- **En contra**: hay más servicios en Docker, conservar varias versiones del índice ocupa espacio en Postgres y exige disciplina para etiquetar cada versión.
