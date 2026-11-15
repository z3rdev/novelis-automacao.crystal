import { ArrowRight, ExternalLink, Monitor, UserRound } from "lucide-react";
import type { ReportTicket } from "@/services/execution-reports";
import { desktop } from "@/services/desktop";
import { fmtBRL, fmtDateTime, fmtTime } from "@/lib/format";
import { Button } from "@/components/ui/button";

export function DailyReportTicket({ ticket }: { ticket: ReportTicket }) {
  const amount = fmtBRL(ticket.valor ?? null);
  const time = Number.isFinite(Date.parse(ticket.confirmado_em))
    ? fmtTime(ticket.confirmado_em).slice(0, 5)
    : "—";
  return (
    <article className="daily-ticket" aria-label={`CT-e ${ticket.cte}`}>
      <time
        className="daily-ticket-time"
        dateTime={ticket.confirmado_em}
        title={fmtDateTime(ticket.confirmado_em)}
      >
        {time}
      </time>
      <div className="daily-ticket-body">
        <div className="daily-ticket-top">
          <h3>
            <span className="text-muted-foreground">CT-e</span> {ticket.cte}
          </h3>
          {ticket.link ? (
            <Button
              variant="ghost"
              size="sm"
              className="daily-ticket-link"
              aria-label={`Abrir chamado ${ticket.numero}`}
              onClick={() => void desktop.openPath(ticket.link)}
            >
              {ticket.numero || "Abrir chamado"}
              <ExternalLink className="h-3.5 w-3.5" />
            </Button>
          ) : (
            <span className="text-xs text-muted-foreground">
              {ticket.numero || "Chamado sem número"}
            </span>
          )}
        </div>
        <div className="daily-ticket-route-value">
          <div
            className="daily-ticket-route"
            title={`${ticket.origem || "Origem não informada"} → ${ticket.destino || "Destino não informado"}`}
          >
            <span>{ticket.origem || "Origem não informada"}</span>
            <ArrowRight className="h-3.5 w-3.5 shrink-0" />
            <span>{ticket.destino || "Destino não informado"}</span>
          </div>
          <span className="daily-ticket-amount" aria-label={`Valor do CT-e: ${amount}`}>
            {amount}
          </span>
        </div>
        <div className="daily-ticket-meta">
          <div className="daily-ticket-freight">
            <span>
              {ticket.ton
                ? `${ticket.ton.replace(/\.0+$/, "").replace(".", ",")} t`
                : "Tonelagem —"}
            </span>
            <span>Tarifa {ticket.id_tarifa || "—"}</span>
          </div>
          <div className="daily-ticket-operator">
            <span title={ticket.operator || "Operador não informado"}>
              <UserRound />
              {ticket.operator || "Operador não informado"}
            </span>
            <span title={ticket.computer || "Computador não informado"}>
              <Monitor />
              {ticket.computer || "Computador não informado"}
            </span>
          </div>
        </div>
      </div>
    </article>
  );
}
