import { describe, expect, it } from "vitest";
import { summarizeHealth } from "./health";

const live = { status: "ok", version: "0.1.0", git_sha: "abc1234", environment: "local" } as const;

describe("summarizeHealth", () => {
  it("is offline when the liveness probe fails", () => {
    expect(summarizeHealth({ live: null, ready: null }).state).toBe("offline");
  });

  it("is degraded and names the failing checks when the backend is not ready", () => {
    const summary = summarizeHealth({
      live,
      ready: { status: "not_ready", checks: { database: false } },
    });

    expect(summary.state).toBe("degraded");
    expect(summary.detail).toContain("database");
  });

  it("is online with the version fingerprint when everything is ready", () => {
    const summary = summarizeHealth({
      live,
      ready: { status: "ready", checks: { database: true } },
    });

    expect(summary.state).toBe("online");
    expect(summary.detail).toContain("abc1234");
  });
});
