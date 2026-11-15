import { useQuery } from "@tanstack/react-query";
import {
  ExternalLink,
  Copy,
  Ticket,
  CalendarDays,
  UserRound,
  MapPin,
  RefreshCw,
} from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { useApi, type Chamado } from "@/services";
import { desktop } from "@/services/desktop";
import { Pill } from "./status";
import { chamadoStates } from "./chamado-status";
import { fmtBRL, fmtDateTime, fmtDate } from "@/lib/format";
import { toast } from "sonner";

export function ChamadoDrawer({
  selected,
  onClose,
}: {
  selected: Chamado | null;
  onClose(): void;
}) {
  const { api, mode, baseUrl } = useApi();
  const identifier = selected?.id ?? selected?.cte;
  const detail = useQuery({
    queryKey: ["chamado-detail", mode, baseUrl, identifier],
    queryFn: () => api.getChamado(identifier!),
    enabled: Boolean(identifier),
    retry: 0,
    refetchInterval: identifier ? 30000 : false,
  });
  const value = selected ? { ...selected, ...detail.data } : null;
  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      toast.success("Copiado");
    } catch {
      toast.error("Não foi possível copiar o conteúdo.");
    }
  }
  const [tone, label, Icon] = value ? chamadoStates[value.andamento] : chamadoStates.na_fila;
  return (
    <Sheet
      open={Boolean(selected)}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <SheetContent className="w-full overflow-y-auto p-0 sm:max-w-xl">
        {value && (
          <>
            <SheetHeader className="border-b bg-primary/5 px-7 pb-7 pt-9">
              <span className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-teal-500/10 text-teal-700">
                <Ticket className="h-5 w-5" />
              </span>
              <SheetTitle className="break-all text-2xl">
                Chamado {value.chamado || "não identificado"}
              </SheetTitle>
              <SheetDescription className="font-mono">CT-e {value.cte}</SheetDescription>
              <div className="pt-3">
                <Pill tone={tone} icon={Icon}>
                  {value.statusOriginal || label}
                </Pill>
              </div>
            </SheetHeader>
            <div className="space-y-7 p-7">
              <div className="flex flex-wrap gap-2">
                <Button
                  disabled={!value.portalUrl}
                  onClick={() =>
                    value.portalUrl &&
                    void desktop
                      .openPath(value.portalUrl)
                      .catch(() => toast.error("Não foi possível abrir o portal."))
                  }
                >
                  <ExternalLink />
                  Abrir chamado no Novelis
                </Button>
                <Button
                  variant="outline"
                  disabled={!value.chamado}
                  onClick={() => value.chamado && void copy(value.chamado)}
                >
                  <Copy />
                  Copiar número
                </Button>
              </div>
              {detail.isFetching && (
                <p className="flex items-center gap-2 text-xs text-muted-foreground">
                  <RefreshCw className="h-3 w-3 animate-spin" />
                  Conferindo informações do chamado…
                </p>
              )}
              {detail.isError && (
                <p role="alert" className="text-sm text-destructive">
                  Não foi possível carregar os detalhes. {(detail.error as Error).message}
                </p>
              )}
              {!value.portalUrl && !detail.isFetching && !detail.isError && (
                <p className="text-xs text-muted-foreground">
                  O vínculo direto não está disponível neste registro.
                </p>
              )}
              <dl className="grid grid-cols-2 gap-x-5 gap-y-6 text-sm">
                <div>
                  <dt className="mb-1.5 flex items-center gap-1.5 text-xs text-muted-foreground">
                    <CalendarDays className="h-3.5 w-3.5" />
                    Abertura no Novelis
                  </dt>
                  <dd>{fmtDateTime(value.aberturaNovelis)}</dd>
                </div>
                <div>
                  <dt className="mb-1.5 flex items-center gap-1.5 text-xs text-muted-foreground">
                    <UserRound className="h-3.5 w-3.5" />
                    Responsável
                  </dt>
                  <dd className="break-words">{value.responsavel || "Não informado"}</dd>
                </div>
                <div>
                  <dt className="mb-1.5 text-xs text-muted-foreground">Data do registro</dt>
                  <dd>{fmtDate(value.data)}</dd>
                </div>
                <div>
                  <dt className="mb-1.5 text-xs text-muted-foreground">Valor total</dt>
                  <dd>{fmtBRL(value.valorTotal)}</dd>
                </div>
                <div>
                  <dt className="mb-1.5 text-xs text-muted-foreground">ID tarifário</dt>
                  <dd className="break-all font-mono">{value.idTarifario || "Não informado"}</dd>
                </div>
                <div>
                  <dt className="mb-1.5 text-xs text-muted-foreground">JDA</dt>
                  <dd className="break-all font-mono">{value.jda || "Não informado"}</dd>
                </div>
              </dl>
              <section className="space-y-3 rounded-xl border bg-muted/20 p-4 text-sm">
                <h3 className="flex items-center gap-2 font-medium">
                  <MapPin className="h-4 w-4 text-teal-600" />
                  Percurso
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="mb-1 text-xs text-muted-foreground">Origem</p>
                    {value.origem || "Não informada"}
                  </div>
                  <div>
                    <p className="mb-1 text-xs text-muted-foreground">Destino</p>
                    {value.destino || "Não informado"}
                  </div>
                </div>
              </section>
              <section className="space-y-2">
                <h3 className="text-sm font-medium">Chave de acesso do CT-e</h3>
                <p className="break-all rounded-lg bg-muted p-3 font-mono text-xs leading-6">
                  {value.chave || "Não informada na fonte"}
                </p>
                {value.chave && (
                  <Button variant="ghost" size="sm" onClick={() => void copy(value.chave!)}>
                    <Copy />
                    Copiar chave
                  </Button>
                )}
              </section>
              {value.descricao && (
                <section>
                  <h3 className="mb-2 text-sm font-medium">Informações adicionais</h3>
                  <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-muted-foreground">
                    {value.descricao}
                  </p>
                </section>
              )}
              <p className="border-t pt-4 text-xs text-muted-foreground">
                Sincronizado no Cargo Hub em {fmtDateTime(value.sincronizadoEm)}. A abertura do
                portal pode exigir autenticação.
              </p>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
