import { ExternalLink, CheckCircle2, AlertTriangle } from "lucide-react";
import { type CteTariffAudit, cteTariffLabels } from "@/services/cte-tariff";
import { Pill } from "./status";
import { Button } from "@/components/ui/button";
import { fmtBRL, fmtDate, fmtDateTime } from "@/lib/format";
import { desktop } from "@/services/desktop";

export const auditMoney = (value: string | null | undefined) =>
  value == null ? "—" : fmtBRL(Number(value));
export function CteTariffStatus({ value }: { value: CteTariffAudit | null | undefined }) {
  if (!value) return <Pill tone="neutral">Não conferido</Pill>;
  return (
    <Pill
      tone={
        value.status === "conferido"
          ? "success"
          : value.status === "indisponivel"
            ? "neutral"
            : "warning"
      }
      icon={value.status === "conferido" ? CheckCircle2 : AlertTriangle}
    >
      {cteTariffLabels[value.status]}
    </Pill>
  );
}
export function CteTariffPanel({ value }: { value: CteTariffAudit | null | undefined }) {
  if (!value) return null;
  const ref = value.selecionada;
  return (
    <section className="space-y-4 border-t pt-5" aria-label="Conferência tarifária">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold">Conferência tarifária</h3>
        <CteTariffStatus value={value} />
      </div>
      {ref && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-muted/50 p-3">
          <div>
            <div className="font-medium">
              Tarifa {ref.idTarifa} · Rota {ref.idRota}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {ref.veiculo} · {auditMoney(ref.tarifaTon)}/t
            </div>
          </div>
          <Button
            size="sm"
            variant="ghost"
            onClick={() =>
              void desktop.openPath(
                `https://novelis.wtmh.com.br/tarifa/rota_add/${ref.idRota}/${ref.idTarifa}`,
              )
            }
          >
            <ExternalLink />
            Portal
          </Button>
        </div>
      )}
      <div className="overflow-x-auto rounded-md border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-xs text-muted-foreground">
            <tr>
              <th className="p-2 text-left font-medium">Informação</th>
              <th className="p-2 text-right font-medium">Observação / SQL</th>
              <th className="p-2 text-right font-medium">Tarifário</th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-t">
              <td className="p-2">TON</td>
              <td
                className={`p-2 text-right tabular-nums ${value.tonConfere === false ? "text-warning-foreground" : ""}`}
              >
                {value.tonObservacao === null ? "Não informada" : `${value.tonObservacao} t`}
              </td>
              <td className="p-2 text-right tabular-nums">
                {ref?.capacidadeTon ? `${ref.capacidadeTon} t` : "—"}
              </td>
            </tr>
            <tr className="border-t">
              <td className="p-2">Frete base</td>
              <td
                className={`p-2 text-right tabular-nums ${value.freteConfere === false ? "text-warning-foreground" : ""}`}
              >
                {auditMoney(value.freteSql)}
              </td>
              <td className="p-2 text-right tabular-nums">{auditMoney(ref?.valorTotal)}</td>
            </tr>
            <tr className="border-t">
              <td className="p-2">Total CT-e</td>
              <td className="p-2 text-right tabular-nums">{auditMoney(value.totalSql)}</td>
              <td className="p-2 text-right tabular-nums">{auditMoney(value.totalReferencia)}</td>
            </tr>
          </tbody>
        </table>
      </div>
      {value.diferencaFrete !== null && Number(value.diferencaFrete) !== 0 && (
        <p className="text-sm text-warning-foreground">
          Diferença no frete: <strong>{auditMoney(value.diferencaFrete)}</strong>
        </p>
      )}
      <dl className="grid grid-cols-2 gap-3 text-xs">
        <div>
          <dt className="text-muted-foreground">FREVAL (SQL)</dt>
          <dd className="mt-1">{auditMoney(value.frevalSql)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Outros (SQL)</dt>
          <dd className="mt-1">{auditMoney(value.outrosSql)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">ID da observação</dt>
          <dd className="mt-1">{value.idObservacao ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Percurso da observação</dt>
          <dd className="mt-1">{value.percursoObservacao ?? "—"}</dd>
        </div>
      </dl>
      <p className="text-xs text-muted-foreground">
        Referência na emissão: {fmtDate(value.dataReferencia)}. Total de referência = frete
        tarifário + FREVAL + outros do SQL.
      </p>
      {!!value.alertas.length && (
        <div
          role="status"
          className="space-y-1 border-l-2 border-amber-400 pl-3 text-xs text-warning-foreground"
        >
          {value.alertas.map((text) => (
            <p key={text}>{text}</p>
          ))}
          <p className="pt-1 text-muted-foreground">Alertas não bloqueiam a abertura do chamado.</p>
        </div>
      )}
      {!ref && !!value.candidatos.length && (
        <div className="space-y-2">
          <h4 className="text-xs font-medium">{value.totalCandidatos} tarifas possíveis</h4>
          {value.candidatos.map((item) => (
            <div
              key={item.id}
              className="flex flex-wrap justify-between gap-2 rounded border p-2 text-xs"
            >
              <span>
                Tarifa {item.idTarifa} · {item.veiculo}
              </span>
              <span>
                {item.capacidadeTon} t · {auditMoney(item.valorTotal)}
              </span>
            </div>
          ))}
        </div>
      )}
      <p className="text-xs text-muted-foreground">
        Catálogo: {fmtDateTime(value.catalogoAtualizadoEm)}
      </p>
    </section>
  );
}
