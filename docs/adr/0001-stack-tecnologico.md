# ADR 0001 · Stack tecnológico del proyecto 01

- **Estado**: aceptado
- **Fecha**: 2026-11-21

## Contexto

El proyecto 01 es la opción A de la propuesta, un asistente de atención y agendamiento multi-agente construido con LangGraph. Es un proyecto de aprendizaje, así que el stack debe enseñar las piezas que piden las empresas, ser agnóstico y open source, correr en local sobre la RTX 5070 Ti y poder desplegarse después en la nube.

Dos requisitos guían la capa de modelos:

- **Coste cero al empezar**: solo modelos locales de Ollama, sin APIs de pago.
- **Modelos intercambiables para experimentar**: el ingeniero debe poder cambiar el modelo de cualquier rol con una línea y comparar resultados con datos. El usuario final nunca elige modelo, y el de producción se decide con esas mediciones.

Las versiones se verificaron en PyPI, npm y Docker Hub el 21 de noviembre de 2026.

## Decisión

### Backend

| Pieza | Elección | Versión |
|---|---|---|
| Lenguaje | Python | 3.13 |
| Proyecto y dependencias | uv con workspace y lockfile | 0.13 |
| API | FastAPI, Pydantic v2, pydantic-settings | 0.165 · 2.14 · 2.16 |
| Streaming | SSE con sse-starlette | 3.7 |
| ORM y migraciones | SQLAlchemy 2 asíncrono y Alembic | 2.1 · 1.20 |
| Driver de Postgres | psycopg 3, el mismo que usa el checkpointer de LangGraph | 3.3 |
| Logs | loguru en JSON con request_id, como en mlops-housing-api | 0.8 |
| Calidad | ruff, mypy en modo estricto, pytest, testcontainers | 0.17 · 2.4 · 9.2 · 4.15 |

### Agente

| Pieza | Elección | Versión |
|---|---|---|
| Orquestación | LangGraph | 1.2 |
| Modelos y mensajes | langchain-core con `init_chat_model` e `init_embeddings`, y langchain para `create_agent` con middleware desde F4 | 1.8 · 1.5 |
| Persistencia del grafo | langgraph-checkpoint-postgres con `AsyncPostgresSaver` y `PostgresStore` | 3.2 |
| Proveedor activo | langchain-ollama | 1.1 |
| Proveedores opcionales | langchain-openai y langchain-anthropic como extras que no se instalan hasta necesitarlos | 1.8 · 1.7 |
| Parsing de documentos | Docling | 2.151 |
| MCP | SDK oficial `mcp` para el servidor y langchain-mcp-adapters para consumir | 2.3 · 0.3 |

### Capa de modelos intercambiable

Ningún nodo del grafo conoce al proveedor. Cada nodo pide un **rol**, una fábrica traduce el rol al modelo configurado y devuelve un `BaseChatModel` de LangChain. Solo el ingeniero cambia esta configuración, y puede hacerlo con una línea de tres formas:

- **En `.env`**, para todo el entorno: `MODEL_AGENDA=ollama:qwen3.8-27b:iq4-xs`
- **En una corrida de evals**, para comparar varios a la vez: `just eval agenda "ollama:qwen3.8-27b:iq3-xxs,ollama:gemma4-26b:q2-k-xl"`
- **En un notebook o un test**: `graph = build_graph(models={"agenda": "ollama:qwen3.8-27b:iq4-xs"})`

```toml
# config/models.toml, leído con pydantic-settings
[roles]
supervisor = "local_general"
atencion   = "local_general"
agenda     = "local_general"
auditor    = "local_general"

[models.local_general]
provider          = "ollama"
model             = "qwen3.8-27b:iq3-xxs"
tools             = true
structured_output = "json_schema"
context_window    = 32768

# Se activa solo cuando quieras medir cuánto mejora un modelo de pago
# [models.api_openai]
# provider = "openai"
# model    = "el que se elija en ese momento"

[embeddings]
provider   = "ollama"
model      = "bge-m3"
dimensions = 1024
```

Reglas de la capa:

- **Capacidades declaradas**: cada modelo declara si soporta tools, cómo hace salida estructurada y su ventana de contexto, de modo que las diferencias entre proveedores quedan aisladas en la fábrica y no en los nodos.
- **Embeddings versionados**: cada vector guarda el nombre del modelo que lo generó. Cambiar de modelo de embeddings obliga a reindexar, porque los vectores de modelos distintos no son comparables.
- **Prompts por modelo cuando haga falta**: un prompt afinado para Qwen puede rendir distinto en otro modelo, por eso los evals de F5 son la condición para aceptar un cambio de proveedor.
- **Coste medido**: cuando entre un proveedor de pago, Langfuse registra tokens y coste por petición y promptfoo compara calidad, latencia y precio entre modelos.

### Modelos iniciales, todos locales

| Uso | Modelo | Notas |
|---|---|---|
| LLM para todos los roles | `qwen3.8-27b:iq3-xxs` | 10 GB, soporta tools y thinking según `ollama show` |
| Candidatos a comparar | `qwen3.8-27b:iq4-xs` y `gemma4-26b:q2-k-xl` | La iq4-xs da más calidad pero ocupa 14 GB; la Q2_K de Gemma pierde bastante precisión por la cuantización |
| Embeddings | bge-m3 o qwen3-embedding | Hay que descargarlo; se elige con un eval de recuperación en F2 |
| Reranker | Cross-encoder local como bge-reranker-v2-m3 | Se mide si basta con CPU para no competir por la VRAM |

Estrategia de VRAM: con 16 GB solo cabe un LLM grande a la vez, y cambiar de modelo en Ollama cuesta segundos de carga. Por lo tanto todos los roles comparten el mismo LLM con prompts distintos, se mantiene cargado con `keep_alive` y junto a él solo viven el modelo de embeddings y el reranker, que son pequeños.

### Principio de diseño para modelos locales

El LLM decide poco y el código hace mucho. Los modelos locales son menos fiables que los de pago en tool calling y en razonamiento largo, de modo que el grafo compensa con diseño:

- **Salida estructurada restringida**: Ollama acepta un JSON Schema en `format` y obliga al modelo a respetarlo, así que el supervisor y el auditor nunca devuelven texto libre.
- **Pocas tools y simples**: el agente de agenda extrae intención y datos de la cita; la validación de horarios y la escritura en base de datos las hace código determinista.
- **Pasos cortos y explícitos** en el grafo en lugar de un agente que razone muchos pasos seguidos.

### Estrategia de recuperación

La calidad del RAG depende más de recuperar los fragmentos correctos que del tamaño del modelo, porque si el contexto correcto no llega ningún modelo puede responder bien. Por eso la inversión principal va a la búsqueda:

1. **Parsing estructurado** con Docling, que respeta títulos, tablas y listas.
2. **Chunking por estructura** en secciones y cláusulas reales, no por número fijo de palabras.
3. **Contexto en cada fragmento**: se antepone a cada chunk el título del documento y de su sección para que el embedding sepa de qué trata.
4. **Búsqueda híbrida**: pgvector para similitud semántica y full-text search de Postgres en español para coincidencias exactas como nombres de servicios o precios, combinados con Reciprocal Rank Fusion.
5. **Reranking** de los mejores candidatos con un cross-encoder.
6. **Reescritura de la consulta** cuando la pregunta es ambigua o depende de la conversación.
7. **Filtros por metadatos**, por ejemplo por sede o tipo de servicio.
8. **Evaluación separada**: métricas de recuperación como recall@k y MRR por un lado, y fidelidad de la respuesta por otro, para saber si un fallo viene de la búsqueda o del modelo.

### Laboratorio de modelos

La pregunta de si un modelo más inteligente vale la pena no tiene una respuesta global, porque cambia según el rol. Es probable que el supervisor no gane nada con un modelo mayor y que el auditor sí. Por eso cada rol tiene su propio dataset y sus propias métricas.

| Rol | Qué se mide |
|---|---|
| Supervisor | Exactitud al clasificar la intención |
| Agente de atención | Recall@k de la búsqueda y fidelidad de la respuesta a los documentos |
| Agente de agenda | Exactitud al extraer servicio, fecha y hora, y tasa de tool calls válidas |
| Auditor | Porcentaje de respuestas con errores sembrados que detecta, y falsos positivos |
| Conversación completa | Tareas terminadas con éxito en diálogos de varios turnos |

En cada corrida se registran también:

- **Fiabilidad**: JSON inválido, reintentos y timeouts.
- **Rendimiento**: latencia p50 y p95, tiempo hasta el primer token, tokens por segundo y VRAM.
- **Coste por tarea completada**: tokens por precio en los modelos de pago; en local se registra el tiempo de GPU.

Método:

1. **Dataset dorado** del negocio ficticio, con 50 a 100 casos por rol, generado con ayuda del modelo local y revisado a mano.
2. **Varias repeticiones por caso**, porque los LLM no son deterministas, e intervalos de confianza con bootstrap para distinguir una mejora real del ruido.
3. **Casos de ajuste separados de los casos de prueba**, para no afinar los prompts hasta memorizar el dataset.
4. **Experimentos en Langfuse**: cada corrida queda enlazada a sus trazas, de modo que se puede abrir el caso que falló y ver por qué.
5. **Decisión registrada en un ADR**, por ejemplo que el auditor justifica un modelo mayor y el supervisor no.

Si en algún momento quieres medir la distancia frente a un modelo de pago, basta activarlo solo para una corrida de evals. El laboratorio arranca pequeño en F1 con el supervisor y crece en cada fase, sin esperar a F5.

### Datos

- Postgres 18 con pgvector 0.8.7, imagen `pgvector/pgvector:pg18`. Una sola base guarda los datos del negocio, los vectores, los checkpoints y la memoria de largo plazo.

### Frontend

| Pieza | Elección | Versión |
|---|---|---|
| Framework | Next.js con App Router, React, TypeScript estricto | 16.4 · 19.3 |
| Estilos y componentes | Tailwind CSS y shadcn/ui | 4.3 · 4.23 |
| Chat | AI SDK con `useChat`; FastAPI emite su protocolo de stream y los pasos del agente y las confirmaciones viajan como data parts | 7.0 |
| Contrato con el API | Tipos generados desde el OpenAPI de FastAPI con openapi-typescript | 7.13 |
| Pantallas de gestión | TanStack Query para agenda y documentos | — |
| Herramientas | pnpm, Biome, Vitest, Playwright | — · 2.6 · 5.1 · 1.65 |

### LLMOps

- **Langfuse autoalojado**: trazas, prompts versionados y datasets de evaluación. Su despliegue trae varios servicios propios, por eso va en un perfil de Compose aparte.
- **promptfoo 0.126**: matriz de comparación entre modelos y red teaming de prompt injection.
- **RAGAS 0.4**: métricas de calidad del RAG. Como juez se usa el mismo modelo local, y se acepta que sea un juez más débil a cambio de coste cero.

### Infraestructura y flujo de trabajo

- Docker Compose con perfiles: `core` con Postgres, `observability` con Langfuse y `app` con backend y frontend en contenedores.
- Ollama nativo en Windows para aprovechar la GPU; los contenedores lo alcanzan por `host.docker.internal`.
- Dockerfiles multi-stage con uv, usuario no root y healthchecks.
- `just` como task runner multiplataforma.
- GitHub Actions con lint, tipos, tests y build de imágenes. Los evals corren en local contra Ollama, ya que los runners de GitHub no tienen GPU.
- pre-commit con ruff, mypy, Biome y detect-secrets.
- Conventional Commits, un tag semver por fase y un ADR por cada decisión relevante.

## Buenas prácticas que seguirá el código

1. **Capas**: api, servicios, dominio e infraestructura. El grafo no conoce FastAPI, y las tools del agente y el servidor MCP llaman a los mismos servicios de dominio.
2. **Estado tipado**: `TypedDict` con reducers para el estado del grafo, y salida estructurada en Pydantic para el enrutamiento y los veredictos del auditor, nunca parseando texto libre.
3. **Tools seguras**: tipadas, con mínimo privilegio y sin text-to-SQL para escribir datos.
4. **Idempotencia**: al reanudar tras un `interrupt`, LangGraph vuelve a ejecutar el nodo desde el principio, por eso crear una cita usa una clave de idempotencia.
5. **Confirmación humana** antes de cualquier efecto irreversible.
6. **Pruebas en tres niveles**: tests deterministas del grafo con modelos falsos, tests de integración con testcontainers y evals separados de los tests.
7. **Prompts versionados** en archivos y después en Langfuse, nunca dispersos en el código.
8. **Trazabilidad desde F0**: un request_id une logs, trazas de Langfuse y respuestas del API.
9. **Datos personales enmascarados** en trazas y logs para cumplir la Ley 1581.
10. **Configuración por entorno** con pydantic-settings, un `.env.example` versionado y los secretos fuera del repositorio.

## Consecuencias

- **A favor**: coste cero, los datos nunca salen del equipo, un solo Postgres simplifica la operación y el laboratorio permite decidir con datos cuándo un modelo más inteligente aporta valor.
- **En contra**: un modelo local cuantizado obliga a diseñar el grafo con más cuidado, el juez local de los evals es menos fiable, Next.js añade curva de aprendizaje, Langfuse autoalojado consume memoria y los 16 GB de VRAM limitan modelo y contexto a la vez.

## Alternativas descartadas

- **APIs de pago desde el inicio**: contradicen el requisito de coste cero; se activan solo para medir la diferencia en el laboratorio.
- **MLflow para los experimentos**: es la herramienta clásica de tracking, pero aquí Langfuse ya une experimentos y trazas. MLflow llega en el proyecto 02 con el modelo de scoring; el detalle está en ADR 0002.
- **Un modelo distinto por rol**: con 16 GB obligaría a cargar y descargar modelos en cada petición.
- **LiteLLM como gateway**: aporta fallbacks y control de costes entre proveedores, pero con un solo proveedor no compensa; se reconsidera en F7.
- **LangGraph Platform o Agent Server**: ofrece menos control y acopla el despliegue al proveedor.
- **Qdrant**: sería otra pieza que operar sin necesidad a esta escala.
- **CopilotKit con AG-UI**: abstrae justo la capa de streaming que se quiere aprender.
- **Streamlit**: se queda corto para un producto real.
- **ty**: sigue en versión 0.0.x.
- **Postgres 19**: está recién publicado, así que se prefiere la madurez de la 18.
