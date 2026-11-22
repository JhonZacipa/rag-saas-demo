import "server-only";
import { createBackendClient } from "./api/client";
import type { HealthInput } from "./health";

const PROBE_TIMEOUT_MS = 3000;

/** Call both health probes. Network errors are reported as "no answer" instead of crashing the page. */
export async function fetchBackendHealth(): Promise<HealthInput> {
  const client = createBackendClient();
  try {
    const [live, ready] = await Promise.all([
      client.GET("/health", { signal: AbortSignal.timeout(PROBE_TIMEOUT_MS) }),
      client.GET("/health/ready", { signal: AbortSignal.timeout(PROBE_TIMEOUT_MS) }),
    ]);
    // A 503 from /health/ready still carries a typed body, exposed as `error`.
    return { live: live.data ?? null, ready: ready.data ?? ready.error ?? null };
  } catch {
    return { live: null, ready: null };
  }
}
