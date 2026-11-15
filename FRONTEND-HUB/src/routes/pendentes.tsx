import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import * as XLSX from "xlsx";
import { Search, Download, CheckCircle2, RefreshCw } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { PageBody, TableBox } from "@/components/app/page";
import { DocPill, Pill } from "@/components/app/status";
import { useApi, type Cte } from "@/services";
import { fmtBRL, fmtDate, fmtDateTime } from "@/lib/format";
import { ConsultationPeriod } from "@/components/app/consultation-period";
import { dateLimits, periodError, type DateRange } from "@/services/consultation";
import { toast } from "sonner";
import { desktop } from "@/services/desktop";
import { CteTariffPanel, CteTariffStatus, auditMoney } from "@/components/app/cte-tariff-panel";
import { RequestGnreLink } from "@/components/app/chat/request-gnre-link";

export const Route = createFileRoute("/pendentes")({
  head: () => ({
    meta: [
      { title: "CT-es pendentes · Automação Novelis" },
      {
        name: "description",
        content: "Pesquise CT-es e veja a situação de PDF, XML, comprovante e chamado.",
      },
      { property: "og:title", content: "CT-es pendentes · Automação Novelis" },
      {
        property: "og:description",
        content: "Pesquise CT-es e veja a situação de PDF, XML, comprovante e chamado.",
      },
    ],
  }),
  component: Pendentes,
});

type Filtro = "todos" | "pdf" | "xml" | "comprovante" | "pronto" | "bloqueado";
const lbl = (s: string) =>
  ({ disponivel: "Disponível", faltando: "Faltando", nao_exige: "Não exige" })[s] ?? s;
const missing = (c: Cte) =>
  c.pdf === "faltando" || c.xml === "faltando" || c.comprovante === "faltando";

function Pendentes() {
  const { api, mode, baseUrl } = useApi();
  const q = useQuery({
    queryKey: ["ctes", mode, baseUrl],
    queryFn: () => api.listCtes(),
    refetchInterval: 2000,
    refetchOnWindowFocus: "always",
    retry: 0,
  });
  const [busca, setBusca] = useState("");
  const [filtro, setFiltro] = useState<Filtro>("todos");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const sel = q.data?.find((item) => item.id === selectedId) ?? null;
  const [period, setPeriod] = useState(2);
  const [range, setRange] = useState<DateRange>(() => ({
    dataInicio: dateLimits().max,
    dataFim: dateLimits().max,
  }));
  const qc = useQueryClient();
  const refresh = useMutation({
    mutationFn: () =>
      api.refreshCtes(period === -1 ? 0 : period, period === -1 ? range : undefined),
    onSuccess: () => {
      toast.success("Consulta iniciada");
      qc.invalidateQueries();
    },
    onError: (error: Error) => toast.error(error.message),
  });
  const rows = useMemo(
    () =>
      (q.data ?? []).filter((c) => {
        const b = busca.trim().toLowerCase();
        if (
          b &&
          !(
            c.id.includes(b) ||
            c.chave.includes(b) ||
            c.destinatario.toLowerCase().includes(b) ||
            c.destino.toLowerCase().includes(b)
          )
        )
          return false;
        return (
          filtro === "todos" ||
          (filtro === "pdf" && c.pdf === "faltando") ||
          (filtro === "xml" && c.xml === "faltando") ||
          (filtro === "comprovante" && c.comprovante === "faltando") ||
          (filtro === "pronto" && c.prontoChamado) ||
          (filtro === "bloqueado" && !c.prontoChamado)
        );
      }),
    [q.data, busca, filtro],
  );
  const count = (f: (c: Cte) => boolean) => (q.data ?? []).filter(f).length;

  function exportar(soFaltantes: boolean) {
    const data = (soFaltantes ? (q.data ?? []).filter(missing) : rows).map((c) => ({
      "CT-e": c.id,
      "Chave de acesso": c.chave,
      Emissão: fmtDate(c.emissao),
      "Valor (R$)": c.valor,
      Destinatário: c.destinatario,
      Origem: c.origem,
      Destino: c.destino,
      PDF: lbl(c.pdf),
      XML: lbl(c.xml),
      "Guia/Comprovante": lbl(c.comprovante),
      "Pronto p/ chamado": c.prontoChamado ? "Sim" : "Não",
      "TON observação": c.tariffAudit?.tonObservacao,
      "TON tarifário": c.tariffAudit?.selecionada?.capacidadeTon,
      "ID tarifário": c.tariffAudit?.selecionada?.idTarifa,
      "Frete SQL": c.tariffAudit?.freteSql,
      "Frete tarifário": c.tariffAudit?.selecionada?.valorTotal,
      Conferência: c.tariffAudit?.status,
    }));
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(data), "CT-es");
    const out = XLSX.write(wb, { type: "array", bookType: "xlsx" });
    desktop.saveFile(
      `ctes_${soFaltantes ? "faltantes" : "todos"}_${new Date().toISOString().slice(0, 10)}.xlsx`,
      new Blob([out]),
    );
  }

  return (
    <PageBody>
      <div className="flex flex-wrap items-baseline gap-3">
        <h2 className="text-xl font-semibold">Fila de abertura</h2>
        <span className="text-sm text-muted-foreground">
          {q.data?.length ?? 0} CT-es sem chamado
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <ConsultationPeriod
          value={period}
          onChange={setPeriod}
          range={range}
          onRangeChange={setRange}
          disabled={refresh.isPending}
        >
          <Button
            variant="outline"
            size="sm"
            onClick={() => refresh.mutate()}
            disabled={refresh.isPending || (period === -1 && Boolean(periodError(range)))}
          >
            <RefreshCw />
            Consultar CT-es
          </Button>
          <span className="text-xs text-muted-foreground">
            Arquivos verificados{" "}
            {q.dataUpdatedAt ? new Date(q.dataUpdatedAt).toLocaleTimeString("pt-BR") : "—"}
          </span>
        </ConsultationPeriod>
      </div>
      {q.isError && (
        <p role="alert" className="text-sm text-destructive">
          Verificação de arquivos indisponível. {(q.error as Error).message}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative w-full max-w-sm">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            className="pl-8"
            placeholder="Buscar CT-e, chave, destinatário…"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
          />
        </div>
        <ToggleGroup
          type="single"
          variant="outline"
          size="sm"
          value={filtro}
          onValueChange={(v) => v && setFiltro(v as Filtro)}
          className="flex-wrap"
        >
          <ToggleGroupItem value="todos">Todos ({count(() => true)})</ToggleGroupItem>
          <ToggleGroupItem value="pdf">
            Sem PDF ({count((c) => c.pdf === "faltando")})
          </ToggleGroupItem>
          <ToggleGroupItem value="xml">
            Sem XML ({count((c) => c.xml === "faltando")})
          </ToggleGroupItem>
          <ToggleGroupItem value="comprovante">
            Sem comprovante ({count((c) => c.comprovante === "faltando")})
          </ToggleGroupItem>
          <ToggleGroupItem value="pronto">
            Prontos ({count((c) => c.prontoChamado)})
          </ToggleGroupItem>
          <ToggleGroupItem value="bloqueado">
            Bloqueados ({count((c) => !c.prontoChamado)})
          </ToggleGroupItem>
        </ToggleGroup>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button size="sm" variant="outline" className="ml-auto">
              <Download />
              Exportar Excel
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => exportar(false)}>
              Lista filtrada ({rows.length})
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => exportar(true)}>
              Apenas com documentos faltantes
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <TableBox maxH="max-h-[calc(100vh-11rem)]">
        <Table className="min-w-[1400px]">
          <TableHeader>
            <TableRow>
              <TableHead>CT-e</TableHead>
              <TableHead>Emissão</TableHead>
              <TableHead>Origem / destino</TableHead>
              <TableHead>TON obs. / tarifa</TableHead>
              <TableHead>ID tarifa</TableHead>
              <TableHead className="text-right">Frete SQL / tarifa</TableHead>
              <TableHead>Conferência</TableHead>
              <TableHead>PDF</TableHead>
              <TableHead>XML</TableHead>
              <TableHead>Guia/Comprovante</TableHead>
              <TableHead className="w-px whitespace-nowrap">Chamado</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((c) => (
              <TableRow
                key={c.id}
                className="cursor-pointer"
                onClick={() => setSelectedId(c.id)}
                data-state={sel?.id === c.id ? "selected" : undefined}
              >
                <TableCell className="font-mono font-medium">{c.id}</TableCell>
                <TableCell>{fmtDate(c.emissao)}</TableCell>
                <TableCell className="whitespace-nowrap">
                  {c.tariffAudit?.origem || c.origem}
                  <span className="px-2 text-muted-foreground">→</span>
                  {c.tariffAudit?.destino || c.destino}
                </TableCell>
                <TableCell className="whitespace-nowrap tabular-nums font-normal">
                  {c.tariffAudit?.tonObservacao ?? "—"} /{" "}
                  {c.tariffAudit?.selecionada?.capacidadeTon ?? "—"} t
                </TableCell>
                <TableCell className="font-mono">
                  {c.tariffAudit?.selecionada?.idTarifa ?? "—"}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  <div>{auditMoney(c.tariffAudit?.freteSql)}</div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {auditMoney(c.tariffAudit?.selecionada?.valorTotal)}
                  </div>
                </TableCell>
                <TableCell>
                  <CteTariffStatus value={c.tariffAudit} />
                </TableCell>
                <TableCell>
                  <DocPill s={c.pdf} />
                </TableCell>
                <TableCell>
                  <DocPill s={c.xml} />
                </TableCell>
                <TableCell>
                  <DocPill s={c.comprovante} />
                </TableCell>
                <TableCell className="w-px whitespace-nowrap">
                  {c.prontoChamado ? (
                    <Pill tone="success" icon={CheckCircle2}>
                      Pronto
                    </Pill>
                  ) : (
                    <Pill tone="warning">Aguardando</Pill>
                  )}
                </TableCell>
              </TableRow>
            ))}
            {!rows.length && (
              <TableRow>
                <TableCell colSpan={11} className="py-10 text-center text-muted-foreground">
                  {q.isLoading
                    ? "Carregando…"
                    : q.isError
                      ? "Sem conexão com o backend."
                      : "Nenhum CT-e encontrado para os filtros."}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableBox>
      <Sheet open={!!sel} onOpenChange={(o) => !o && setSelectedId(null)}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
          {sel && (
            <>
              <SheetHeader>
                <SheetTitle className="font-mono">CT-e {sel.id}</SheetTitle>
                <SheetDescription>
                  Filial {sel.filial} · Série {sel.serie} · Número {sel.numero}
                </SheetDescription>
              </SheetHeader>
              <div className="space-y-4 px-4 pb-6 text-sm">
                <div>
                  <div className="text-xs text-muted-foreground">Chave de acesso</div>
                  <div className="break-all font-mono text-xs">{sel.chave}</div>
                </div>
                <dl className="grid grid-cols-2 gap-3">
                  <div>
                    <dt className="text-xs text-muted-foreground">Emissão</dt>
                    <dd>{fmtDateTime(sel.emissao)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted-foreground">Valor</dt>
                    <dd>{fmtBRL(sel.valor)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted-foreground">Origem</dt>
                    <dd>{sel.origem}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted-foreground">Destino</dt>
                    <dd>{sel.destino}</dd>
                  </div>
                  <div className="col-span-2">
                    <dt className="text-xs text-muted-foreground">Destinatário</dt>
                    <dd>{sel.destinatario}</dd>
                  </div>
                </dl>
                <div className="space-y-2 rounded-md border p-3">
                  <div className="flex justify-between">
                    <span>PDF (DACTE)</span>
                    <DocPill s={sel.pdf} />
                  </div>
                  <div className="flex justify-between">
                    <span>XML</span>
                    <DocPill s={sel.xml} />
                  </div>
                  <div className="flex justify-between">
                    <span>Guia/Comprovante</span>
                    <DocPill s={sel.comprovante} />
                  </div>
                  <div className="flex justify-between border-t pt-2 font-medium">
                    <span>Pronto para chamado</span>
                    {sel.prontoChamado ? (
                      <Pill tone="success">Sim</Pill>
                    ) : (
                      <Pill tone="warning">Não</Pill>
                    )}
                  </div>
                </div>
                {!sel.prontoChamado && (
                  <p className="text-xs text-warning-foreground">
                    Falta:{" "}
                    {[
                      sel.pdf === "faltando" && "PDF",
                      sel.xml === "faltando" && "XML",
                      sel.comprovante === "faltando" && "comprovante",
                    ]
                      .filter(Boolean)
                      .join(", ")}
                    .
                  </p>
                )}
                <CteTariffPanel value={sel.tariffAudit} />
                <RequestGnreLink cte={sel.id} />
                <div>
                  <div className="mb-1 text-xs font-medium text-muted-foreground">Histórico</div>
                  <ol className="space-y-1 border-l pl-3">
                    {sel.historico.map((h, i) => (
                      <li key={i}>
                        <span className="text-xs text-muted-foreground">{fmtDateTime(h.data)}</span>{" "}
                        — {h.evento}
                      </li>
                    ))}
                  </ol>
                </div>
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </PageBody>
  );
}
