import { connection } from "next/server";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchBackendHealth } from "@/lib/backend-health";
import { type ServiceState, summarizeHealth } from "@/lib/health";

const BADGE_VARIANT: Record<ServiceState, "default" | "secondary" | "destructive"> = {
  online: "default",
  degraded: "secondary",
  offline: "destructive",
};

/** Server component that renders the live backend status on every request. */
export async function BackendStatus() {
  // Render at request time: the status must never be frozen at build time.
  await connection();
  const summary = summarizeHealth(await fetchBackendHealth());

  return (
    <Card>
      <CardHeader>
        <CardTitle>Estado del backend</CardTitle>
        <CardDescription>{summary.detail}</CardDescription>
      </CardHeader>
      <CardContent>
        <Badge variant={BADGE_VARIANT[summary.state]}>{summary.label}</Badge>
      </CardContent>
    </Card>
  );
}

export function BackendStatusSkeleton() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Estado del backend</CardTitle>
        <CardDescription>Comprobando…</CardDescription>
      </CardHeader>
      <CardContent>
        <Badge variant="outline">…</Badge>
      </CardContent>
    </Card>
  );
}
