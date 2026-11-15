import { ExternalLink } from "lucide-react";
import type { DiagnosticEvent } from "@/services/remote-diagnostics";
import { desktop } from "@/services/desktop";
import { fmtDateTime } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Pill } from "../status";

export function TechnicalDetails({ value }: { value: unknown }) {
  return (
    <details className="diagnostic-technical">
      <summary>Detalhes técnicos</summary>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}

function httpCode(value: unknown) {
  return typeof value === "number" ? value : "Não registrado";
}

export function DiagnosticEvents({
  events,
  http = false,
}: {
  events: DiagnosticEvent[];
  http?: boolean;
}) {
  if (!events.length)
    return (
      <p className="diagnostic-empty">
        {http
          ? "Nenhuma evidência HTTP no período consultado."
          : "Nenhum evento relevante registrado."}
      </p>
    );
  return (
    <div className="divide-y">
      {events.map((event, index) => {
        const detail = event.details;
        const confirmed = detail["status"] === "confirmed";
        const url =
          typeof detail["url"] === "string" &&
          /^https:\/\/novelis\.wtmh\.com\.br\/portal\/chamado\/\d+$/.test(detail["url"])
            ? detail["url"]
            : null;
        return (
          <article key={`${event.time}:${index}`} className="diagnostic-event">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">
                  {http ? `CT-e ${detail["cte"] ?? "não informado"}` : event.source}
                </span>
                <Pill
                  tone={confirmed ? "success" : event.severity === "error" ? "error" : "neutral"}
                >
                  {confirmed ? "Confirmado" : String(detail["status"] ?? event.severity)}
                </Pill>
              </div>
              <time className="text-xs text-muted-foreground">{fmtDateTime(event.time)}</time>
            </div>
            <p className="mt-2 break-words text-sm">{event.message}</p>
            {http && (
              <dl className="diagnostic-http-fields">
                <div>
                  <dt>Envio HTTP</dt>
                  <dd>{httpCode(detail["save_http"])}</dd>
                </div>
                <div>
                  <dt>Leitura HTTP</dt>
                  <dd>{httpCode(detail["readback_http"])}</dd>
                </div>
                <div>
                  <dt>Confirmação</dt>
                  <dd>{String(detail["confirmation_source"] ?? "Não registrada")}</dd>
                </div>
                <div>
                  <dt>Anexos visíveis</dt>
                  <dd>
                    {detail["attachments_visible"] === true
                      ? "Sim"
                      : detail["attachments_visible"] === false
                        ? "Não"
                        : "Não verificado"}
                  </dd>
                </div>
              </dl>
            )}
            {Array.isArray(detail["attachments"]) && (
              <p className="mt-2 break-words text-xs text-muted-foreground">
                {detail["attachments"].map(String).join(" · ")}
              </p>
            )}
            {url && (
              <Button
                size="sm"
                variant="ghost"
                className="mt-2"
                onClick={() => void desktop.openPath(url)}
              >
                Chamado {String(detail["number"] ?? detail["numeroChamado"] ?? "")}
                <ExternalLink />
              </Button>
            )}
            <TechnicalDetails value={event} />
          </article>
        );
      })}
    </div>
  );
}
