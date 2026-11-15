import { Download, Loader2 } from "lucide-react";
import type { DiagnosticRequest, DiagnosticState } from "@/services/remote-diagnostics";
import { diagnosticCheckLabels, diagnosticStateLabels } from "@/services/remote-diagnostics";
import { fmtDateTime } from "@/lib/format";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Pill, type Tone } from "../status";
import { DiagnosticEvents, TechnicalDetails } from "./diagnostic-events";

export function DiagnosticStatePill({ state }: { state: DiagnosticState }) {
  const tone: Tone =
    state === "completed"
      ? "success"
      : ["failed", "timed_out"].includes(state)
        ? "error"
        : state === "running"
          ? "info"
          : "neutral";
  return <Pill tone={tone}>{diagnosticStateLabels[state]}</Pill>;
}

export function DiagnosticReportPanel({
  open,
  value,
  error,
  onClose,
  onDownload,
}: {
  open: boolean;
  value: DiagnosticRequest | undefined;
  error: string | undefined;
  onClose(): void;
  onDownload(value: DiagnosticRequest): void;
}) {
  const report = value?.result;
  return (
    <Sheet open={open} onOpenChange={(active) => !active && onClose()}>
      <SheetContent className="diagnostic-report-panel w-full gap-0 overflow-hidden p-0 sm:max-w-[900px]">
        <SheetHeader className="shrink-0 border-b p-6 pr-12 text-left">
          <SheetTitle>Diagnóstico · {value?.computer_name ?? "Carregando…"}</SheetTitle>
          <SheetDescription>
            {value
              ? `Solicitado ${fmtDateTime(value.requested_at)} · ${value.requested_by}`
              : "Consultando solicitação"}
          </SheetDescription>
          {value && (
            <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
              <div className="flex items-center gap-2">
                <DiagnosticStatePill state={value.state} />
                {report && !report.complete && <Pill tone="warning">Parcial</Pill>}
              </div>
              <Button
                size="sm"
                variant="outline"
                disabled={!report}
                onClick={() => onDownload(value)}
              >
                <Download />
                Baixar JSON
              </Button>
            </div>
          )}
        </SheetHeader>
        <div className="min-h-0 flex-1 overflow-y-auto p-6">
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          {!report && (
            <div className="diagnostic-empty">
              {value?.state === "queued" || value?.state === "running" ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" />
                  <p>
                    {value.state === "queued"
                      ? "Aguardando o computador atender à solicitação."
                      : "O computador está verificando o ambiente e as últimas execuções."}
                  </p>
                </>
              ) : (
                <p>
                  {value?.state === "expired"
                    ? "O cliente não respondeu dentro do prazo. Verifique a conexão e a versão instalada."
                    : value?.state === "failed" || value?.state === "timed_out"
                      ? "A coleta não foi concluída. Uma nova solicitação pode ser feita quando o computador estiver disponível."
                      : "Carregando diagnóstico…"}
                </p>
              )}
            </div>
          )}
          {report && (
            <Tabs defaultValue="summary">
              <TabsList className="mb-5 flex h-auto flex-wrap justify-start gap-1">
                <TabsTrigger value="summary">Resumo</TabsTrigger>
                <TabsTrigger value="runs">Execuções ({report.runs.length})</TabsTrigger>
                <TabsTrigger value="http">HTTP ({report.http.length})</TabsTrigger>
                <TabsTrigger value="environment">Ambiente</TabsTrigger>
              </TabsList>
              <TabsContent value="summary">
                <dl className="diagnostic-summary">
                  <div>
                    <dt>Execuções</dt>
                    <dd>{report.summary.runs}</dd>
                  </div>
                  <div>
                    <dt>Com falha</dt>
                    <dd>{report.summary.failed_runs}</dd>
                  </div>
                  <div>
                    <dt>Chamados confirmados</dt>
                    <dd>{report.summary.confirmed_tickets}</dd>
                  </div>
                  <div>
                    <dt>Verificações com atenção</dt>
                    <dd>{report.summary.issues}</dd>
                  </div>
                </dl>
                <div className="my-5 space-y-2 text-xs text-muted-foreground">
                  <p>
                    {report.device.windows_user} · versão {report.device.version}
                  </p>
                  <p>
                    Coletado {fmtDateTime(report.checked_at)} · últimas {report.scope.max_runs}{" "}
                    execuções em {report.scope.days_back} dias
                  </p>
                  {!report.complete && (
                    <p className="text-warning-foreground">
                      A coleta foi interrompida; os dados já obtidos foram preservados.
                    </p>
                  )}
                  {(report.events_truncated || report.http_truncated) && (
                    <p className="text-warning-foreground">
                      O limite de eventos foi atingido; esta é uma amostra do histórico.
                    </p>
                  )}
                </div>
                <div className="divide-y rounded-md border">
                  {report.checks.map((item) => (
                    <div key={item.id} className="flex items-start justify-between gap-4 p-3">
                      <div>
                        <p className="text-sm font-medium">{item.title}</p>
                        <p className="mt-1 text-xs text-muted-foreground">{item.message}</p>
                      </div>
                      <Pill
                        tone={
                          item.status === "ok"
                            ? "success"
                            : item.status === "failed"
                              ? "error"
                              : item.status === "not_tested"
                                ? "neutral"
                                : "warning"
                        }
                      >
                        {diagnosticCheckLabels[item.status]}
                      </Pill>
                    </div>
                  ))}
                </div>
                <p className="mt-4 text-xs text-muted-foreground">
                  O HTTP apresentado é histórico. Esta solicitação não envia chamados nem gera
                  documentos fiscais.
                </p>
              </TabsContent>
              <TabsContent value="runs">
                <div className="divide-y">
                  {report.runs.map((run) => (
                    <section key={run.id} className="py-4 first:pt-0">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <h3 className="text-sm font-medium">
                          {run.flow} · {run.id.slice(0, 8)}
                        </h3>
                        <Pill
                          tone={
                            run.status === "failed"
                              ? "error"
                              : run.status === "completed"
                                ? "success"
                                : "neutral"
                          }
                        >
                          {run.status}
                        </Pill>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {fmtDateTime(run.started_at)} → {fmtDateTime(run.finished_at)}
                      </p>
                      <p className="my-2 text-sm">{run.message}</p>
                      <DiagnosticEvents events={run.events} />
                      {run.events_truncated && (
                        <p className="text-xs text-warning-foreground">
                          Exibidos até 100 eventos relevantes desta execução.
                        </p>
                      )}
                    </section>
                  ))}
                </div>
                {!report.runs.length && (
                  <p className="diagnostic-empty">
                    Nenhuma execução encontrada para esta máquina no período.
                  </p>
                )}
              </TabsContent>
              <TabsContent value="http">
                <DiagnosticEvents events={report.http} http />
              </TabsContent>
              <TabsContent value="environment">
                <div className="divide-y">
                  {report.checks.map((item) => (
                    <section key={item.id} className="py-4 first:pt-0">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <h3 className="text-sm font-medium">{item.title}</h3>
                        <span className="text-xs text-muted-foreground">
                          {item.source === "live" ? "Verificação atual" : "Registro anterior"} ·{" "}
                          {fmtDateTime(item.checked_at)}
                        </span>
                      </div>
                      <p className="mt-2 text-sm">{item.message}</p>
                      <TechnicalDetails value={item.details} />
                    </section>
                  ))}
                </div>
              </TabsContent>
            </Tabs>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
