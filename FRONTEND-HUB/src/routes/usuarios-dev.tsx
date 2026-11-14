import { createFileRoute } from "@tanstack/react-router";
import { DeveloperMonitorPage } from "@/components/app/developer-monitor";

export const Route = createFileRoute("/usuarios-dev")({
  head: () => ({ meta: [{ title: "Usuários e dispositivos · Cargo Hub" }] }),
  component: DeveloperMonitorPage,
});
