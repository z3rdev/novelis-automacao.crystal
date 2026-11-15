import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  FileText,
  FileCode2,
  Receipt,
  Ticket,
  ListChecks,
  Play,
  RefreshCw,
  Activity,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageBody, Kpi, Section } from "@/components/app/page";
import { useRun, RunSummary, StagesView, isBusy } from "@/components/app/run-panel";
import { OverviewConsultAction } from "@/components/app/overview-consult-action";
import { useApi } from "@/services";
import { fmtDateTime } from "@/lib/format";
import { toast } from "sonner";
import { useState } from "react";
import { ConsultationPeriod } from "@/components/app/consultation-period";
import { dateLimits, periodError, type DateRange } from "@/services/consultation";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Visão geral · Automação Novelis" },
      {
        name: "description",
        content: "Indicadores de CT-es pendentes, documentos faltantes e situação da execução.",
      },
      { property: "og:title", content: "Visão geral · Automação Novelis" },
      {
        property: "og:description",
        content: "Indicadores de CT-es pendentes, documentos faltantes e situação da execução.",
      },
    ],
  }),
  component: Overview,
});

function Overview() {
  const { api, mode, baseUrl } = useApi();
  const qc = useQueryClient();
  const [period, setPeriod] = useState(30);
  const [range, setRange] = useState<DateRange>(() => ({
    dataInicio: dateLimits().max,
    dataFim: dateLimits().max,
  }));
  const ov = useQuery({
    queryKey: ["overview", mode, baseUrl],
    queryFn: () => api.getOverview(),
    refetchInterval: 5000,
    retry: 0,
  });
  const run = useRun();
  const refresh = useMutation({
    mutationFn: () =>
      api.refreshCtes(period === -1 ? 0 : period, period === -1 ? range : undefined),
    onSuccess: (r) => {
      toast.success(
        r.state === "executando"
          ? "Consulta iniciada. Acompanhe o progresso em Execução."
          : `Consulta concluída: ${r.atualizados} CT-e(s)`,
      );
      qc.invalidateQueries();
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const d = ov.data;
  const currentRun = run.data ?? d?.execucao;
  const v = (n?: number) => (d ? n : "…");
  return (
    <PageBody>
      {ov.isError && (
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-warning/30 bg-warning/10 p-3 text-sm"
        >
          <p>
            {(ov.error as Error).message}{" "}
            {d ? "Exibindo os últimos dados recebidos." : "Aguardando os dados do backend."}
          </p>
          <Button size="sm" variant="outline" onClick={() => ov.refetch()} disabled={ov.isFetching}>
            <RefreshCw className={ov.isFetching ? "animate-spin" : ""} />
            Tentar novamente
          </Button>
        </div>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          Última atualização dos dados:{" "}
          <strong className="text-foreground">{fmtDateTime(d?.ultimaAtualizacao)}</strong>
        </p>
        <div className="ml-auto">
          <ConsultationPeriod
            value={period}
            onChange={setPeriod}
            range={range}
            onRangeChange={setRange}
            disabled={refresh.isPending || isBusy(currentRun)}
          >
            <OverviewConsultAction
              run={currentRun}
              refreshing={refresh.isPending}
              invalid={period === -1 && Boolean(periodError(range))}
              onConsult={() => refresh.mutate()}
            />
            <Button size="sm" asChild>
              <Link to="/execucao">
                <Play />
                Ir para execução
              </Link>
            </Button>
          </ConsultationPeriod>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Kpi label="CT-es na fila" value={v(d?.naFila)} icon={ListChecks} tone="info" />
        <Kpi
          label="PDFs faltantes"
          value={v(d?.pdfFaltando)}
          icon={FileText}
          tone={d?.pdfFaltando ? "warning" : "success"}
        />
        <Kpi
          label="XMLs faltantes"
          value={v(d?.xmlFaltando)}
          icon={FileCode2}
          tone={d?.xmlFaltando ? "warning" : "success"}
        />
        <Kpi
          label="Comprovantes faltantes"
          value={v(d?.comprovanteFaltando)}
          icon={Receipt}
          tone={d?.comprovanteFaltando ? "warning" : "success"}
        />
        <Kpi label="Prontos p/ chamado" value={v(d?.prontosChamado)} icon={Ticket} tone="success" />
        <Kpi
          label="Execução atual"
          value={
            <span className="text-base">
              {run.data
                ? {
                    aguardando: "Ociosa",
                    executando: "Executando",
                    parando: "Parando",
                    concluida: "Concluída",
                    falhou: "Falhou",
                    cancelada: "Cancelada",
                  }[run.data.state]
                : "…"}
            </span>
          }
          icon={Activity}
          tone={
            run.data?.state === "executando"
              ? "info"
              : run.data?.state === "falhou"
                ? "error"
                : "neutral"
          }
          hint={run.data?.id ?? "Nenhum lote em andamento"}
        />
      </div>
      {run.data && (
        <Section
          title="Execução atual"
          actions={
            <Button variant="ghost" size="sm" asChild>
              <Link to="/monitor">Abrir monitor</Link>
            </Button>
          }
        >
          <div className="space-y-4">
            <RunSummary run={run.data} />
            <StagesView run={run.data} />
          </div>
        </Section>
      )}
      <div className="grid gap-3 md:grid-cols-3">
        {[
          {
            to: "/pendentes" as const,
            t: "Conferir pendências",
            d: "Veja o que falta em cada CT-e e exporte para Excel.",
            i: ListChecks,
          },
          {
            to: "/documentos" as const,
            t: "Gerar DACTE",
            d: "Gere os PDFs faltantes pelo banco de dados e Crystal Reports.",
            i: FileText,
          },
          {
            to: "/chamados" as const,
            t: "Chamados Novelis",
            d: "Acompanhe abertura, JDA e solução dos chamados.",
            i: Ticket,
          },
        ].map((c) => (
          <Link
            key={c.to}
            to={c.to}
            className="group flex gap-3 rounded-md border bg-card p-4 hover:border-primary"
          >
            <c.i className="mt-0.5 h-5 w-5 text-primary" />
            <div>
              <div className="text-sm font-semibold group-hover:text-primary">{c.t}</div>
              <div className="text-xs text-muted-foreground">{c.d}</div>
            </div>
          </Link>
        ))}
      </div>
    </PageBody>
  );
}
