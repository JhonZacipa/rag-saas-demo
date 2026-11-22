import type { components } from "./api/schema";

type Liveness = components["schemas"]["HealthResponse"];
type Readiness = components["schemas"]["ReadinessResponse"];

export type ServiceState = "online" | "degraded" | "offline";

export interface HealthInput {
  live: Liveness | null;
  ready: Readiness | null;
}

export interface HealthSummary {
  state: ServiceState;
  label: string;
  detail: string;
}

/** Turn the raw probe results into what the UI shows. Pure, so it is easy to test. */
export function summarizeHealth({ live, ready }: HealthInput): HealthSummary {
  if (!live) {
    return {
      state: "offline",
      label: "Sin conexión",
      detail: "El backend no responde.",
    };
  }

  if (ready?.status !== "ready") {
    const failing = Object.entries(ready?.checks ?? {})
      .filter(([, ok]) => !ok)
      .map(([name]) => name);
    return {
      state: "degraded",
      label: "Degradado",
      detail:
        failing.length > 0
          ? `El backend responde, pero fallan: ${failing.join(", ")}.`
          : "El backend responde, pero no se pudo verificar si está listo.",
    };
  }

  return {
    state: "online",
    label: "En línea",
    detail: `Versión ${live.version} · commit ${live.git_sha} · entorno ${live.environment}.`,
  };
}
