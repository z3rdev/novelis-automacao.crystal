import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useRef, useState } from "react";
import * as XLSX from "xlsx";
import { Play, Square, Upload, CalendarRange, ListPlus, AlertTriangle, CheckCircle2, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageBody, Section } from "@/components/app/page";
import { PeriodSelect } from "@/components/app/period-select";
import { Pill, flowLabel } from "@/components/app/status";
import { useRun, useRunActions, isBusy, RunSummary, StagesView } from "@/components/app/run-panel";
import { parseCteList } from "@/lib/format";
import type { FlowId } from "@/services";
import { toast } from "sonner";

export const Route = createFileRoute("/execucao")({
  head: () => ({ meta: [
    { title: "Execução e lotes · Automação Novelis" },
    { name: "description", content: "Inicie, acompanhe e pare lotes de processamento de CT-es." },
    { property: "og:title", content: "Execução e lotes · Automação Novelis" },
    { property: "og:description", content: "Inicie, acompanhe e pare lotes de processamento de CT-es." },
  ] }),
  component: Execucao,
});

function Execucao() {
  const run = useRun();
  const { start, stop } = useRunActions();
  const [flow, setFlow] = useState<FlowId>("completo");
  const [origem, setOrigem] = useState<"auto" | "manual">("auto");
  const [dias, setDias] = useState(30);
  const [texto, setTexto] = useState("");
  const [arquivo, setArquivo] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const parsed = useMemo(() => parseCteList(texto.split(/[\n;,\t]+/)), [texto]);
  const busy = isBusy(run.data) || start.isPending || stop.isPending;

  async function importar(f: File) {
    try {
      const wb = XLSX.read(await f.arrayBuffer(), { type: "array" });
      const rows = XLSX.utils.sheet_to_json<string[]>(wb.Sheets[wb.SheetNames[0] ?? ""]!, { header: 1, raw: false });
      const vals = rows.flat().map((v) => String(v ?? "")).filter((v) => /\d+-\d+-\d+/.test(v));
      setTexto(vals.join("\n")); setArquivo(f.name); setOrigem("manual");
      toast.success(`${vals.length} valor(es) lidos de ${f.name}`);
    } catch { toast.error("Não foi possível ler o arquivo. Use .xlsx, .xlsm ou .csv."); }
  }

  function iniciar(): void {
    if (busy) { toast.error("Já existe uma execução em andamento. Aguarde ou pare antes de iniciar outra."); return; }
    if (origem === "manual") {
      if (!parsed.validos.length) { toast.error("Informe ao menos um CT-e válido (filial-série-número)."); return; }
      start.mutate({ flow, ctes: parsed.validos });
    } else start.mutate({ flow, periodoDias: dias });
  }

  return (
    <PageBody>
      <div className="grid items-start gap-4 xl:grid-cols-[minmax(280px,340px)_minmax(0,1fr)] 2xl:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
        <Section title="Novo lote">
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label>Fluxo</Label>
              <Select value={flow} onValueChange={(v) => setFlow(v as FlowId)} disabled={busy}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{(Object.keys(flowLabel) as FlowId[]).map((f) => <SelectItem key={f} value={f}>{flowLabel[f]}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <Tabs value={origem} onValueChange={(v) => setOrigem(v as "auto" | "manual")}>
              <TabsList className="grid h-auto w-full grid-cols-1 gap-1 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2"><TabsTrigger value="auto" className="flex-1"><CalendarRange />Consulta automática</TabsTrigger><TabsTrigger value="manual" className="flex-1"><ListPlus />Lista de CT-es</TabsTrigger></TabsList>
              <TabsContent value="auto" className="space-y-1.5 pt-2">
                <Label>Período da consulta</Label>
                <PeriodSelect value={dias} onChange={setDias} disabled={busy} />
                <p className="text-xs text-muted-foreground">{dias === 0 ? "CT-es emitidos hoje." : "O período inclui o dia atual."}</p>
              </TabsContent>
              <TabsContent value="manual" className="space-y-2 pt-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="lista">CT-es (um por linha, ex.: 2-10-10001)</Label>
                  <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()} disabled={busy}><Upload />Importar</Button>
                  <input ref={fileRef} type="file" accept=".xlsx,.xlsm,.csv" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) importar(f); e.target.value = ""; }} />
                </div>
                <Textarea id="lista" rows={8} className="font-mono text-sm" placeholder={"2-10-10001\n2-10-10008"} value={texto} onChange={(e) => { setTexto(e.target.value); setArquivo(null); }} disabled={busy} />
                {arquivo && <p className="text-xs text-muted-foreground">Importado de <strong>{arquivo}</strong></p>}
                {texto.trim() && (
                  <div className="space-y-1.5 text-xs">
                    <div className="flex flex-wrap gap-1.5">
                      <Pill tone="success" icon={CheckCircle2}>{parsed.validos.length} válido(s)</Pill>
                      {parsed.duplicados.length > 0 && <Pill tone="warning" icon={Copy}>{parsed.duplicados.length} duplicado(s) ignorado(s)</Pill>}
                      {parsed.invalidos.length > 0 && <Pill tone="error" icon={AlertTriangle}>{parsed.invalidos.length} inválido(s)</Pill>}
                    </div>
                    {parsed.invalidos.length > 0 && <p className="text-destructive">Inválidos: <span className="font-mono">{parsed.invalidos.slice(0, 8).join(", ")}{parsed.invalidos.length > 8 ? "…" : ""}</span></p>}
                    {parsed.duplicados.length > 0 && <p className="text-warning-foreground">Duplicados: <span className="font-mono">{parsed.duplicados.slice(0, 8).join(", ")}</span></p>}
                  </div>
                )}
              </TabsContent>
            </Tabs>
            <div className="flex gap-2 border-t pt-4">
              <Button className="flex-1" onClick={iniciar} disabled={busy}><Play />{start.isPending ? "Enviando…" : "Iniciar"}</Button>
              <Button variant="destructive" className="flex-1" onClick={() => stop.mutate()} disabled={run.data?.state !== "executando" || stop.isPending}><Square />Parar</Button>
            </div>
            {isBusy(run.data) && <p className="text-xs text-info">Novo envio bloqueado enquanto o lote {run.data?.id} estiver em andamento.</p>}
          </div>
        </Section>
        <Section title={<>Execução atual {run.data?.id && <span className="ml-1 font-mono text-xs text-muted-foreground">{run.data.id}</span>}</>}>
          {run.data ? <div className="space-y-5"><RunSummary run={run.data} /><StagesView run={run.data} /></div> : <p className="text-sm text-muted-foreground">{run.isError ? "Sem conexão com o backend." : "Carregando…"}</p>}
        </Section>
      </div>
    </PageBody>
  );
}
