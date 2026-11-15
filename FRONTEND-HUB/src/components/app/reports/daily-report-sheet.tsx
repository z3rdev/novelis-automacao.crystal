import { useMemo, useState } from "react";
import { Download, Loader2, Search, X } from "lucide-react";
import type { ExecutionReport, ReportTicket } from "@/services/execution-reports";
import { fmtDate, fmtDateTime } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { DailyReportTicket } from "./daily-report-ticket";
import { AppSelect } from "../fields/app-select";
import "./daily-report.css";

const normalize = (value: string) =>
  value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("pt-BR");
const timestamp = (ticket: ReportTicket) => Date.parse(ticket.confirmado_em) || 0;

export function DailyReportSheet({
  open,
  report,
  loading,
  error,
  downloading,
  onClose,
  onDownload,
}: {
  open: boolean;
  report: ExecutionReport | undefined;
  loading: boolean;
  error: string | undefined;
  downloading: boolean;
  onClose(): void;
  onDownload(report: ExecutionReport): void;
}) {
  const [search, setSearch] = useState("");
  const [order, setOrder] = useState("newest");
  const tickets = useMemo(() => {
    const term = normalize(search.trim());
    return (report?.opened ?? [])
      .filter(
        (ticket) =>
          !term ||
          normalize(
            [
              ticket.cte,
              ticket.numero,
              ticket.origem,
              ticket.destino,
              ticket.operator,
              ticket.computer,
              ticket.id_tarifa,
            ]
              .filter(Boolean)
              .join(" "),
          ).includes(term),
      )
      .slice()
      .sort((a, b) =>
        order === "newest" ? timestamp(b) - timestamp(a) : timestamp(a) - timestamp(b),
      );
  }, [report?.opened, search, order]);
  const total = report?.opened?.length ?? 0;
  return (
    <Sheet open={open} onOpenChange={(value) => !value && onClose()}>
      <SheetContent className="daily-report-sheet w-full gap-0 overflow-hidden p-0 sm:max-w-[800px]">
        <SheetHeader className="daily-report-header">
          <SheetTitle className="text-xl">Chamados do dia</SheetTitle>
          <SheetDescription>
            {report ? fmtDate(report.report_date) : "Carregando relatório…"}
          </SheetDescription>
          <div className="daily-report-summary">
            <div className="daily-report-counts">
              <span>
                <strong>{report?.opened_count ?? "—"}</strong> chamados abertos
              </span>
              <span>
                {report?.run_count ?? "—"} {report?.run_count === 1 ? "execução" : "execuções"}
              </span>
            </div>
            <Button
              size="sm"
              disabled={!report || downloading}
              onClick={() => report && onDownload(report)}
            >
              {downloading ? <Loader2 className="animate-spin" /> : <Download />}
              {downloading ? "Baixando…" : "Baixar Excel"}
            </Button>
          </div>
        </SheetHeader>
        <div className="daily-report-toolbar">
          <div className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              aria-label="Buscar chamados do dia"
              placeholder="Buscar CT-e, chamado, rota ou operador…"
              className="pl-9 pr-9"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            {search && (
              <button
                type="button"
                aria-label="Limpar busca"
                className="daily-report-clear"
                onClick={() => setSearch("")}
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
          <AppSelect
            label="Ordenar chamados do dia"
            value={order}
            onValueChange={setOrder}
            className="w-40 shrink-0 text-xs"
            options={[
              { value: "newest", label: "Mais recentes" },
              { value: "oldest", label: "Mais antigos" },
            ]}
          />
        </div>
        <div className="daily-report-scroll" aria-busy={loading}>
          {error && (
            <p role="alert" className="mx-6 my-4 text-sm text-destructive">
              {error}
            </p>
          )}
          {loading && !report ? (
            <p role="status" className="daily-report-empty">
              <Loader2 className="h-5 w-5 animate-spin" />
              Carregando chamados…
            </p>
          ) : (
            <ul className="daily-report-list" aria-label="Chamados abertos">
              {tickets.map((ticket) => (
                <li key={`${ticket.cte}:${ticket.numero}`}>
                  <DailyReportTicket ticket={ticket} />
                </li>
              ))}
            </ul>
          )}
          {!loading && report && !tickets.length && (
            <div className="daily-report-empty">
              <p>
                {total
                  ? "Nenhum chamado corresponde à busca."
                  : "Nenhum chamado confirmado nesta data."}
              </p>
              {search && (
                <Button variant="outline" size="sm" onClick={() => setSearch("")}>
                  Limpar busca
                </Button>
              )}
            </div>
          )}
        </div>
        <footer className="daily-report-footer">
          <span aria-live="polite">
            {tickets.length} de {total} chamados
          </span>
          <span>Atualizado {fmtDateTime(report?.generated_at)}</span>
        </footer>
      </SheetContent>
    </Sheet>
  );
}
