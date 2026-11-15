import { createFileRoute } from "@tanstack/react-router";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { ExternalLink, Square } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { PageBody, Section } from "@/components/app/page";
import { isBusy, useRun, useRunActions, RunSummary, StagesView } from "@/components/app/run-panel";
import { useApi, type LogEntry } from "@/services";
import { ActivityLog } from "@/components/app/activity-log";

export const Route = createFileRoute("/monitor")({
  head: () => ({
    meta: [
      { title: "Monitor ao vivo · Automação Novelis" },
      { name: "description", content: "Etapas e atividades da automação em tempo real." },
      { property: "og:title", content: "Monitor ao vivo · Automação Novelis" },
      { property: "og:description", content: "Etapas e atividades da automação em tempo real." },
    ],
  }),
  component: Monitor,
});

export function Monitor() {
  const { api, mode } = useApi();
  const run = useRun();
  const { stop } = useRunActions();
  const [lastXml, setLastXml] = useState<LogEntry | undefined>();
  const focus = useMutation({
    mutationFn: () => api.focusBrowser(),
    onError: (error: Error) => toast.error(error.message),
  });
  const waitingCaptcha =
    mode === "local" &&
    run.data?.state === "executando" &&
    Boolean(lastXml && lastXml.time >= (run.data.iniciadoEm ?? "")) &&
    lastXml?.source === "xml_sefaz.captcha";
  return (
    <PageBody>
      <Section
        title="Execução atual"
        actions={
          isBusy(run.data) && (
            <Button
              size="sm"
              variant="destructive"
              disabled={stop.isPending || run.data?.state === "parando"}
              onClick={() => stop.mutate()}
            >
              <Square />
              {run.data?.state === "parando" ? "Interrompendo…" : "Parar automação"}
            </Button>
          )
        }
      >
        {run.data ? (
          <div className="space-y-5">
            <RunSummary run={run.data} />
            <StagesView run={run.data} />
          </div>
        ) : (
          <p role="status" className="text-sm text-muted-foreground">
            {run.isError
              ? "Sem conexão com a automação. Tentando novamente…"
              : "Carregando execução…"}
          </p>
        )}
      </Section>
      {waitingCaptcha && (
        <div
          role="status"
          className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-warning-foreground"
        >
          <span>SEFAZ aguardando confirmação do hCaptcha.</span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => focus.mutate()}
            disabled={focus.isPending}
          >
            <ExternalLink />
            Mostrar navegador SEFAZ
          </Button>
        </div>
      )}
      <ActivityLog onLatestXml={setLastXml} />
    </PageBody>
  );
}
