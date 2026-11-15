import { createFileRoute } from "@tanstack/react-router";
import { DiagnosticCenter } from "@/components/app/diagnostics/diagnostic-center";

export const Route = createFileRoute("/diagnosticos-dev")({
  head: () => ({ meta: [{ title: "Central de diagnóstico · Cargo Hub" }] }),
  component: DiagnosticCenter,
});
