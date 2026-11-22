import { Suspense } from "react";
import { BackendStatus, BackendStatusSkeleton } from "@/components/backend-status";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-8 px-6 py-16">
      <header className="space-y-2">
        <p className="text-sm text-muted-foreground">Clínica Dental Sonrisa Clara</p>
        <h1 className="font-heading text-3xl font-semibold tracking-tight">
          Asistente de atención y agendamiento
        </h1>
        <p className="text-muted-foreground">
          Fase F0, cimientos del proyecto. El chat con el agente llega en la fase F1.
        </p>
      </header>

      {/* The header is sent immediately; the status streams in when the backend answers. */}
      <Suspense fallback={<BackendStatusSkeleton />}>
        <BackendStatus />
      </Suspense>
    </main>
  );
}
