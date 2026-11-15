import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Calculator, ExternalLink, ArrowRight } from "lucide-react";
import { useApi } from "@/services";
import { type Tariff, tariffLabels, tariffTones } from "@/services/tariffs";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { fmtBRL, fmtDate, fmtDateTime } from "@/lib/format";
import { desktop } from "@/services/desktop";

export function TariffDrawer({ value, onClose }: { value: Tariff | null; onClose(): void }) {
  const { api, mode } = useApi();
  const [tonnes, setTonnes] = useState("");
  const estimate = useMutation({ mutationFn: () => api.estimateTariff(value!.id, tonnes) });
  useEffect(() => {
    setTonnes("");
    estimate.reset();
  }, [value?.id]);
  const money = (v: string | null) => (v === null ? "—" : fmtBRL(Number(v)));
  return (
    <Sheet open={Boolean(value)} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full overflow-y-auto p-0 sm:max-w-xl">
        {value && (
          <>
            <SheetHeader className="border-b px-6 pb-5 pt-8">
              <SheetTitle>Tarifa {value.idTarifa}</SheetTitle>
              <SheetDescription>
                Rota {value.idRota} · {value.veiculo}
              </SheetDescription>
            </SheetHeader>
            <div className="space-y-6 p-6">
              <div className="flex items-center justify-between gap-3">
                <span className={`rounded border px-2 py-1 text-xs ${tariffTones[value.status]}`}>
                  {tariffLabels[value.status]}
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={mode === "demo"}
                  onClick={() =>
                    void desktop.openPath(
                      `https://novelis.wtmh.com.br/tarifa/rota_add/${value.idRota}/${value.idTarifa}`,
                    )
                  }
                >
                  <ExternalLink />
                  Ver no portal
                </Button>
              </div>
              <div className="rounded-md border p-4 text-sm">
                <div>{value.origem}</div>
                <ArrowRight className="my-2 h-4 w-4 text-muted-foreground" />
                <div>{value.destino}</div>
              </div>
              {!value.presentePortal && (
                <p role="status" className="text-sm text-warning-foreground">
                  Esta tarifa não apareceu na última coleta do portal.
                </p>
              )}
              <dl className="grid grid-cols-2 gap-x-6 gap-y-5 text-sm">
                {[
                  ["Tarifa por tonelada", money(value.tarifaTon)],
                  ["Capacidade do veículo", value.capacidadeTon ? `${value.capacidadeTon} t` : "—"],
                  ["Total informado pelo portal", money(value.valorTotal)],
                  ["adValorem", value.adValorem ?? "—"],
                  ["Início", value.inicio ? fmtDate(value.inicio) : value.inicioPortal || "—"],
                  ["Fim", value.fim ? fmtDate(value.fim) : value.fimPortal || "Sem data final"],
                  ["Operação", value.operacao],
                  ["Transportadora", value.transportadora],
                  ["Filial de faturamento", value.faturamento],
                  ["Grupo de empresas", value.grupoEmpresa],
                  ["Ramo", value.ramo],
                  ["Tipo de transporte", value.tipoTransporte],
                  ["Ranking", value.ranking],
                  ["Share", value.share],
                  ["Outros custos", value.outrosCustos || "—"],
                ].map(([label, text]) => (
                  <div key={label}>
                    <dt className="mb-1 text-xs text-muted-foreground">{label}</dt>
                    <dd className="break-words">{text || "—"}</dd>
                  </div>
                ))}
              </dl>
              <section className="space-y-4 border-y py-5">
                <h3 className="flex items-center gap-2 text-sm font-semibold">
                  <Calculator className="h-4 w-4" />
                  Calcular por tonelagem
                </h3>
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    estimate.mutate();
                  }}
                  className="flex items-end gap-2"
                >
                  <div className="flex-1 space-y-1.5">
                    <label htmlFor="tariff-tonnes" className="text-xs font-medium">
                      Toneladas da carga
                    </label>
                    <Input
                      id="tariff-tonnes"
                      inputMode="decimal"
                      placeholder="Ex.: 27,5"
                      value={tonnes}
                      onChange={(e) => {
                        setTonnes(e.target.value);
                        estimate.reset();
                      }}
                    />
                  </div>
                  <Button type="submit" disabled={!tonnes || estimate.isPending}>
                    {estimate.isPending ? "Calculando…" : "Calcular"}
                  </Button>
                </form>
                {estimate.isError && (
                  <p role="alert" className="text-sm text-destructive">
                    {(estimate.error as Error).message}
                  </p>
                )}
                {estimate.data && (
                  <div className="space-y-2 rounded-md bg-muted/50 p-4">
                    <div className="text-xs text-muted-foreground">
                      {estimate.data.toneladas} t × {money(estimate.data.tarifaTon)}/t
                    </div>
                    <div className="text-2xl font-semibold tabular-nums">
                      {money(estimate.data.valor)}
                    </div>
                    {estimate.data.excedeCapacidade && (
                      <p className="text-xs text-warning-foreground">
                        Tonelagem acima da capacidade cadastrada.
                      </p>
                    )}
                    {estimate.data.status !== "vigente" && (
                      <p className="text-xs text-warning-foreground">
                        Tarifa {tariffLabels[estimate.data.status].toLowerCase()}. Confira a
                        vigência antes de usar.
                      </p>
                    )}
                  </div>
                )}
                <p className="text-xs text-muted-foreground">
                  Tarifa sem ICMS, com pedágio. O cálculo não soma adValorem e outros custos.
                </p>
              </section>
              <p className="text-xs text-muted-foreground">
                Conferida em {fmtDateTime(value.conferidoEm)}
              </p>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
