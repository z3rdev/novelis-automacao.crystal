import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Download, FileSpreadsheet, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { useApi } from "@/services";
import type { ExecutionReport } from "@/services/execution-reports";
import { desktop } from "@/services/desktop";
import { fmtDate, fmtDateTime } from "@/lib/format";
import { DailyReportSheet } from "@/components/app/reports/daily-report-sheet";
import { PageBody, TableBox } from "@/components/app/page";
import { Pill } from "@/components/app/status";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export const Route = createFileRoute("/relatorios")({
  component: ReportsRoute,
  validateSearch: (search: Record<string, unknown>): { report?: string } =>
    typeof search["report"] === "string" ? { report: search["report"] } : {},
});

function ReportsRoute() {
  const { report } = Route.useSearch();
  return <Reports key={report ?? "list"} requestedReport={report ?? null} />;
}

export function Reports({ requestedReport = null }: { requestedReport?: string | null } = {}) {
  const { api, mode, baseUrl } = useApi();
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<string | null>(requestedReport);
  const qc = useQueryClient();
  const key = ["execution-reports", mode, baseUrl];
  const q = useQuery({
    queryKey: [...key, page],
    queryFn: () => api.listExecutionReports(page),
    refetchInterval: 15000,
    retry: 0,
  });
  const detail = useQuery({
    queryKey: [...key, "detail", selected],
    queryFn: () => api.getExecutionReport(selected!),
    enabled: !!selected,
    refetchInterval: 15000,
    retry: 0,
  });
  const download = useMutation({
    mutationFn: async (report: ExecutionReport) => {
      const blob = await api.downloadExecutionReport(report.id);
      await desktop.saveFile(
        `CargoHub-Chamados-${report.report_date ?? report.id.slice(0, 8)}.xlsx`,
        blob,
      );
    },
    onError: (error: Error) => toast.error(error.message),
  });
  const sync = useMutation({
    mutationFn: () => api.syncExecutionReports(),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: key });
      toast.success("Compartilhamento solicitado");
    },
    onError: (error: Error) => toast.error(error.message),
  });
  const report = detail.data;
  return (
    <PageBody>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-baseline gap-3">
          <h2 className="text-xl font-semibold">Relatórios diários</h2>
          <span className="text-sm text-muted-foreground">
            {q.data?.total ?? 0} {q.data?.total === 1 ? "relatório" : "relatórios"}
          </span>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => void q.refetch()}
            disabled={q.isFetching}
          >
            <RefreshCw className={q.isFetching ? "animate-spin" : ""} />
            Atualizar
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={mode === "demo" || sync.isPending}
            onClick={() => sync.mutate()}
          >
            <FileSpreadsheet />
            Sincronizar pendentes
          </Button>
        </div>
      </div>
      {q.isError && (
        <p role="alert" className="text-sm text-destructive">
          {q.error.message}
        </p>
      )}
      <TableBox>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Data</TableHead>
              <TableHead>Chamados abertos</TableHead>
              <TableHead>Operadores</TableHead>
              <TableHead>Execuções</TableHead>
              <TableHead>Atualizado</TableHead>
              <TableHead>Arquivo</TableHead>
              <TableHead className="text-right">Excel</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(q.data?.rows ?? []).map((item) => (
              <TableRow
                key={item.id}
                className="cursor-pointer"
                onClick={() => setSelected(item.id)}
              >
                <TableCell className="whitespace-nowrap">{fmtDate(item.report_date)}</TableCell>
                <TableCell className="tabular-nums">{item.opened_count}</TableCell>
                <TableCell className="max-w-72 truncate" title={item.operator}>
                  {item.operator}
                </TableCell>
                <TableCell className="tabular-nums">{item.run_count}</TableCell>
                <TableCell className="whitespace-nowrap">
                  {fmtDateTime(item.generated_at)}
                </TableCell>
                <TableCell title={item.share_message}>
                  <Pill tone={item.share_status === "shared" ? "info" : "neutral"}>
                    {item.share_status === "shared" ? "MinIO" : "Envio pendente"}
                  </Pill>
                </TableCell>
                <TableCell className="text-right">
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={download.isPending}
                    onClick={(event) => {
                      event.stopPropagation();
                      download.mutate(item);
                    }}
                    aria-label={`Baixar Excel ${fmtDate(item.report_date)}`}
                  >
                    <Download className="h-4 w-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {!q.data?.rows.length && (
              <TableRow>
                <TableCell colSpan={7} className="py-12 text-center text-muted-foreground">
                  {q.isLoading
                    ? "Carregando…"
                    : q.isError
                      ? "Relatórios indisponíveis."
                      : "Nenhum relatório gerado ainda."}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableBox>
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>Página {page + 1} · Compartilhado entre os operadores</span>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" disabled={!page} onClick={() => setPage(page - 1)}>
            Anterior
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={!q.data || (page + 1) * q.data.page_size >= q.data.total}
            onClick={() => setPage(page + 1)}
          >
            Próxima
          </Button>
        </div>
      </div>
      <DailyReportSheet
        key={selected ?? "closed"}
        open={!!selected}
        report={report}
        loading={detail.isLoading}
        error={detail.error?.message}
        downloading={download.isPending}
        onClose={() => setSelected(null)}
        onDownload={(item) => download.mutate(item)}
      />
    </PageBody>
  );
}
