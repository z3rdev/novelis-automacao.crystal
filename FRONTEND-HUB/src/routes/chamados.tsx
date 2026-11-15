import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Search, Ticket, CheckCircle2, Clock, Loader2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageBody, Kpi, TableBox } from "@/components/app/page";
import { Pill } from "@/components/app/status";
import { useApi, type Chamado } from "@/services";
import { ChamadoDrawer } from "@/components/app/chamado-drawer";
import { chamadoStates as and } from "@/components/app/chamado-status";
import { fmtBRL, fmtDate, fmtDateTime } from "@/lib/format";

export const Route = createFileRoute("/chamados")({
  head: () => ({ meta: [
    { title: "Chamados Novelis · Automação Novelis" },
    { name: "description", content: "Acompanhe abertura, andamento e solução dos chamados no portal Novelis." },
    { property: "og:title", content: "Chamados Novelis · Automação Novelis" },
    { property: "og:description", content: "Acompanhe abertura, andamento e solução dos chamados no portal Novelis." },
  ] }),
  component: Chamados,
});

function Chamados() {
  const { api, mode, baseUrl } = useApi();
  const [selected, setSelected] = useState<Chamado | null>(null);
  const [busca, setBusca] = useState("");
  const [termo, setTermo] = useState("");
  const [st, setSt] = useState("todos");
  const [pagina, setPagina] = useState(0);
  useEffect(() => { const timer = window.setTimeout(() => setTermo(busca), 300); return () => clearTimeout(timer); }, [busca]);
  const q = useQuery({ queryKey: ["chamados-page", mode, baseUrl, termo, st, pagina], queryFn: () => api.listChamadosPage({ search: termo, status: st, page: pagina, size: 100 }), refetchInterval: 30000, retry: 0 });
  const counts = q.data?.counts ?? {};
  const total = Object.values(counts).reduce((sum, value) => sum + (value ?? 0), 0);
  const rows = q.data?.rows ?? [];
  const paginas = Math.max(1, Math.ceil((q.data?.total ?? 0) / 100));
  const paginaAtual = q.data?.page ?? pagina;
  const visiveis = rows;
  return (
    <PageBody>
      {q.isError && <p className="text-sm text-destructive">Não foi possível consultar os chamados: {(q.error as Error).message}</p>}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi label="Total" value={total} icon={Ticket} />
        <Kpi label="Na fila" value={counts.na_fila ?? 0} icon={Clock} tone="warning" />
        <Kpi label="Em análise" value={counts.em_analise ?? 0} icon={Loader2} tone="info" />
        <Kpi label="Solucionados" value={counts.solucionado ?? 0} icon={CheckCircle2} tone="success" />
      </div>
      <div className="flex flex-wrap gap-2">
        <div className="relative w-full max-w-sm"><Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" /><Input className="pl-8" placeholder="Buscar CT-e, chamado, JDA, responsável…" value={busca} onChange={(e) => { setBusca(e.target.value); setPagina(0); }} /></div>
        <Select value={st} onValueChange={(v) => { setSt(v); setPagina(0); }}><SelectTrigger className="w-48"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="todos">Todos os andamentos</SelectItem>{Object.entries(and).map(([k, v]) => <SelectItem key={k} value={k}>{v[1]}</SelectItem>)}</SelectContent></Select>
      </div>
      <p className="text-xs text-muted-foreground">{mode === "demo" ? "Exemplo de demonstração" : "Banco de comunicação PostgreSQL"} · 100 registros por página · {q.isFetching ? "Atualizando…" : `Sincronizado: ${fmtDateTime(q.data?.synced_at)}`}</p>
      <TableBox maxH="max-h-[calc(100vh-17rem)]">
        <Table className="min-w-[1200px]">
          <TableHeader><TableRow>{["CT-e", "Data", "Valor total", "Abertura Novelis", "ID tarifário", "Chamado", "JDA", "Andamento", "Responsável", "Origem", "Destino"].map((h) => <TableHead key={h} className={h === "Valor total" ? "text-right" : ""}>{h}</TableHead>)}</TableRow></TableHeader>
          <TableBody>
            {visiveis.map((c) => { const [t, l, I] = and[c.andamento]; return (
              <TableRow key={c.id ?? `${c.cte}-${c.chamado}`} tabIndex={0} className="cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-teal-500" aria-label={`Ver chamado ${c.chamado ?? c.cte}`} onClick={() => setSelected(c)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSelected(c); } }}>
                <TableCell className="whitespace-nowrap font-mono font-medium">{c.cte}</TableCell><TableCell>{fmtDate(c.data)}</TableCell><TableCell className="text-right tabular-nums">{fmtBRL(c.valorTotal)}</TableCell>
                <TableCell className="whitespace-nowrap">{fmtDateTime(c.aberturaNovelis)}</TableCell><TableCell className="font-mono">{c.idTarifario}</TableCell><TableCell className="font-mono">{c.chamado ?? "—"}</TableCell><TableCell className="font-mono">{c.jda ?? "—"}</TableCell>
                <TableCell><Pill tone={t} icon={I}>{l}</Pill></TableCell><TableCell>{c.responsavel}</TableCell><TableCell>{c.origem}</TableCell><TableCell>{c.destino}</TableCell>
              </TableRow>); })}
            {!rows.length && <TableRow><TableCell colSpan={11} className="py-10 text-center text-muted-foreground">{q.isLoading ? "Carregando…" : q.isError ? "Consulta indisponível." : "Nenhum chamado encontrado."}</TableCell></TableRow>}
          </TableBody>
        </Table>
      </TableBox>
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span>{(q.data?.total ?? 0).toLocaleString("pt-BR")} chamado(s) · Página {paginaAtual + 1} de {paginas}</span>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" disabled={q.isFetching || paginaAtual === 0} onClick={() => setPagina(paginaAtual - 1)}>Anterior</Button>
          <Button variant="outline" size="sm" disabled={q.isFetching || paginaAtual + 1 >= paginas} onClick={() => setPagina(paginaAtual + 1)}>Próxima</Button>
        </div>
      </div>
      <ChamadoDrawer selected={selected} onClose={() => setSelected(null)} />
    </PageBody>
  );
}
