import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Search, Ticket, CheckCircle2, Clock, XCircle, Loader2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageBody, Kpi, TableBox } from "@/components/app/page";
import { Pill, type Tone } from "@/components/app/status";
import { useApi, type Chamado } from "@/services";
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

const and: Record<Chamado["andamento"], [Tone, string, React.ComponentType<{ className?: string }>]> = {
  na_fila: ["warning", "Na fila", Clock], aberto: ["info", "Aberto", Loader2], em_analise: ["info", "Em análise", Loader2],
  solucionado: ["success", "Solucionado", CheckCircle2], falhou: ["error", "Falhou", XCircle],
};

function Chamados() {
  const { api, mode, baseUrl } = useApi();
  const q = useQuery({ queryKey: ["chamados", mode, baseUrl], queryFn: () => api.listChamados(), refetchInterval: 4000, retry: 0 });
  const [busca, setBusca] = useState("");
  const [st, setSt] = useState("todos");
  const [pagina, setPagina] = useState(0);
  const all = q.data ?? [];
  const rows = useMemo(() => all.filter((c) => (st === "todos" || c.andamento === st) && (!busca || [c.cte, c.chamado, c.jda, c.idTarifario, c.responsavel, c.destino].some((v) => v?.toLowerCase().includes(busca.toLowerCase())))), [all, busca, st]);
  const n = (f: (c: Chamado) => boolean) => all.filter(f).length;
  const paginas = Math.max(1, Math.ceil(rows.length / 100));
  const paginaAtual = Math.min(pagina, paginas - 1);
  const visiveis = rows.slice(paginaAtual * 100, (paginaAtual + 1) * 100);
  return (
    <PageBody>
      {q.isError && <p className="text-sm text-destructive">Não foi possível consultar os chamados: {(q.error as Error).message}</p>}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi label="Total" value={all.length} icon={Ticket} />
        <Kpi label="Na fila" value={n((c) => c.andamento === "na_fila")} icon={Clock} tone="warning" />
        <Kpi label="Pendentes" value={n((c) => c.andamento === "aberto" || c.andamento === "em_analise" || c.andamento === "falhou")} icon={Loader2} tone="info" hint={`${n((c) => c.andamento === "falhou")} com falha`} />
        <Kpi label="Solucionados" value={n((c) => c.andamento === "solucionado")} icon={CheckCircle2} tone="success" />
      </div>
      <div className="flex flex-wrap gap-2">
        <div className="relative w-full max-w-sm"><Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" /><Input className="pl-8" placeholder="Buscar CT-e, chamado, JDA, responsável…" value={busca} onChange={(e) => { setBusca(e.target.value); setPagina(0); }} /></div>
        <Select value={st} onValueChange={(v) => { setSt(v); setPagina(0); }}><SelectTrigger className="w-48"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="todos">Todos os andamentos</SelectItem>{Object.entries(and).map(([k, v]) => <SelectItem key={k} value={k}>{v[1]}</SelectItem>)}</SelectContent></Select>
      </div>
      <TableBox maxH="max-h-[calc(100vh-17rem)]">
        <Table className="min-w-[1200px]">
          <TableHeader><TableRow>{["CT-e", "Data", "Valor total", "Abertura Novelis", "ID tarifário", "Chamado", "JDA", "Andamento", "Responsável", "Origem", "Destino"].map((h) => <TableHead key={h} className={h === "Valor total" ? "text-right" : ""}>{h}</TableHead>)}</TableRow></TableHeader>
          <TableBody>
            {visiveis.map((c) => { const [t, l, I] = and[c.andamento]; return (
              <TableRow key={c.cte}>
                <TableCell className="font-mono font-medium">{c.cte}</TableCell><TableCell>{fmtDate(c.data)}</TableCell><TableCell className="text-right tabular-nums">{fmtBRL(c.valorTotal)}</TableCell>
                <TableCell className="whitespace-nowrap">{fmtDateTime(c.aberturaNovelis)}</TableCell><TableCell className="font-mono">{c.idTarifario}</TableCell><TableCell className="font-mono">{c.chamado ?? "—"}</TableCell><TableCell className="font-mono">{c.jda ?? "—"}</TableCell>
                <TableCell><Pill tone={t} icon={I}>{l}</Pill></TableCell><TableCell>{c.responsavel}</TableCell><TableCell>{c.origem}</TableCell><TableCell>{c.destino}</TableCell>
              </TableRow>); })}
            {!rows.length && <TableRow><TableCell colSpan={11} className="py-10 text-center text-muted-foreground">{q.isLoading ? "Carregando…" : q.isError ? "Consulta indisponível." : "Nenhum chamado encontrado."}</TableCell></TableRow>}
          </TableBody>
        </Table>
      </TableBox>
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span>{rows.length.toLocaleString("pt-BR")} chamado(s) · Página {paginaAtual + 1} de {paginas}</span>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" disabled={paginaAtual === 0} onClick={() => setPagina(paginaAtual - 1)}>Anterior</Button>
          <Button variant="outline" size="sm" disabled={paginaAtual + 1 >= paginas} onClick={() => setPagina(paginaAtual + 1)}>Próxima</Button>
        </div>
      </div>
    </PageBody>
  );
}
