import "server-only";
import createClient from "openapi-fetch";
import type { paths } from "./schema";

/**
 * Typed client for the FastAPI backend.
 *
 * The types in `schema.d.ts` are generated from the backend OpenAPI schema
 * (`just gen-api`), so a breaking change in the API becomes a type error here.
 * `server-only` makes the build fail if this module is imported from a client
 * component, which keeps BACKEND_URL out of the browser.
 */
export function createBackendClient() {
  return createClient<paths>({
    baseUrl: process.env.BACKEND_URL ?? "http://127.0.0.1:8010",
  });
}
