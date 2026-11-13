import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Database, FileCode2, FileText, QrCode, Barcode, FolderOpen, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageBody, Section, TableBox } from "@/components/app/page";
import { Pill, StagePill, type Tone } from "@/components/app/status";
import { useApi, type DacteJob } from "@/services";
import { desktop } from "@/services/desktop";
import { fmtDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

export const Route = createFileRoute("/documentos")({
  head: () => ({ meta: [
    { title: "Documentos e DACTE · Automação Novelis" },
    { name: "description", content: "Gere DACTEs faltantes e confira QR Code e código de barras." },
    { property: "og:title", content: "Documentos e DACTE · Automação Novelis" },
    { property: "og:description", content: "Gere DACTEs faltantes e confira QR Code e código de barras." },
  ] }),
  component: Documentos,
});

const chk = (v?: string): [Tone, string] => (v === "ok" ? ["success", "OK"] : v === "falha" ? ["error", "Falha"] : ["warning", "Pendente"]);

function Documentos() {
  const { api, mode, baseUrl } = useApi();
  const qc = useQueryClient();
  const ctes = useQuery({ queryKey: ["ctes", mode, baseUrl], queryFn: () => api.listCtes(), refetchInterval: 4000, retry: 0 });
  const jobs = useQuery({ queryKey: ["jobs", mode, baseUrl], queryFn: () => api.listDacteJobs(), refetchInterval: 1500, retry: 0 });
  const [metodo, setMetodo] = useState<"crystal" | "xml">("crystal");
  const [marcados, setMarcados] = useState<string[]>([]);
  const [view, setView] = useState<DacteJob | null>(null);
  const faltando = (ctes.data ?? []).filter((c) => c.pdf === "faltando");
  const gen = useMutation({ mutationFn: () => api.generateDacte(marcados, metodo), onSuccess: () => { toast.info(`Geração de ${marcados.length} DACTE(s) enviada — processamento sequencial`); setMarcados([]); qc.invalidateQueries(); }, onError: (e: Error) => toast.error(e.message) });
  const cur = view ?? jobs.data?.find((j) => j.state === "concluida") ?? null;
  const cte = cur && ctes.data?.find((c) => c.id === cur.cte);

  return (
    <PageBody>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,480px)]">
        <div className="space-y-4">
          <Section title={`PDFs faltantes (${faltando.length})`} actions={<Button size="sm" disabled={!marcados.length || gen.isPending} onClick={() => gen.mutate()}><Play />Gerar {marcados.length || ""} DACTE(s)</Button>}>
            <RadioGroup value={metodo} onValueChange={(v) => setMetodo(v as "crystal" | "xml")} className="mb-3 grid gap-2 sm:grid-cols-2">
              {[{ v: "crystal", i: Database, t: "Banco de dados + Crystal Reports", d: "Consulta SQL e relatório DACTE_v4.rpt. Método padrão." }, { v: "xml", i: FileCode2, t: "XML arquivado", d: "Monta o DACTE a partir do XML já salvo na pasta." }].map((o) => (
                <Label key={o.v} htmlFor={`m-${o.v}`} className={cn("flex cursor-pointer gap-3 rounded-md border p-3 font-normal", metodo === o.v && "border-primary bg-accent")}>
                  <RadioGroupItem id={`m-${o.v}`} value={o.v} className="mt-0.5" disabled={mode !== "demo" && o.v === "xml"} />
                  <div><div className="flex items-center gap-1.5 font-semibold"><o.i className="h-4 w-4" />{o.t}</div><div className="text-xs text-muted-foreground">{o.d}</div></div>
                </Label>
              ))}
            </RadioGroup>
            {mode !== "demo" && <p className="mb-3 text-xs text-muted-foreground">Geração em lote pelo Crystal. A alternativa XML ainda não está integrada nesta tela.</p>}
            {(ctes.isError || jobs.isError) && <p className="mb-3 text-sm text-destructive">Não foi possível carregar os documentos do backend.</p>}
            <TableBox maxH="max-h-64">
              <Table><TableHeader><TableRow><TableHead className="w-8"><Checkbox checked={!!faltando.length && marcados.length === faltando.length} onCheckedChange={(v) => setMarcados(v ? faltando.map((c) => c.id) : [])} aria-label="Selecionar todos" /></TableHead><TableHead>CT-e</TableHead><TableHead>XML disponível</TableHead><TableHead>Destino</TableHead></TableRow></TableHeader>
                <TableBody>{faltando.map((c) => (
                  <TableRow key={c.id}><TableCell><Checkbox checked={marcados.includes(c.id)} onCheckedChange={(v) => setMarcados((m) => (v ? [...m, c.id] : m.filter((x) => x !== c.id)))} aria-label={`Selecionar ${c.id}`} /></TableCell><TableCell className="font-mono">{c.id}</TableCell><TableCell>{c.xml === "disponivel" ? <Pill tone="success">Sim</Pill> : <Pill tone="warning">Não</Pill>}</TableCell><TableCell>{c.destino}</TableCell></TableRow>
                ))}{!faltando.length && <TableRow><TableCell colSpan={4} className="py-6 text-center text-muted-foreground">Nenhum PDF faltando.</TableCell></TableRow>}</TableBody>
              </Table>
            </TableBox>
          </Section>
          <Section title="Gerações recentes">
            <TableBox maxH="max-h-80">
              <Table className="min-w-[640px]"><TableHeader><TableRow><TableHead>CT-e</TableHead><TableHead>Método</TableHead><TableHead>Situação</TableHead><TableHead>Etapa / erro</TableHead><TableHead>QR</TableHead><TableHead>Barras</TableHead><TableHead>Data</TableHead></TableRow></TableHeader>
                <TableBody>{(jobs.data ?? []).map((j, i) => (
                  <TableRow key={j.cte + i} className="cursor-pointer" onClick={() => setView(j)} data-state={cur === j ? "selected" : undefined}>
                    <TableCell className="font-mono">{j.cte}</TableCell><TableCell>{j.metodo === "crystal" ? "Crystal" : "XML"}</TableCell><TableCell><StagePill s={j.state} /></TableCell>
                    <TableCell className={cn("max-w-[200px] truncate", j.erro && "text-destructive")}>{j.erro ?? j.etapa}</TableCell>
                    <TableCell><Pill tone={chk(j.qrCode)[0]}>{chk(j.qrCode)[1]}</Pill></TableCell><TableCell><Pill tone={chk(j.codigoBarras)[0]}>{chk(j.codigoBarras)[1]}</Pill></TableCell><TableCell className="whitespace-nowrap">{fmtDateTime(j.geradoEm)}</TableCell>
                  </TableRow>
                ))}</TableBody>
              </Table>
            </TableBox>
          </Section>
        </div>
        <Section title="Visualizador de DACTE" actions={cur?.pdfUrl && <Button size="sm" variant="outline" onClick={() => desktop.openPath(cur.pdfUrl!).catch((e: Error) => toast.error(e.message))}><FolderOpen />Abrir PDF</Button>}>
          {cur ? (
            <div className="space-y-3">
              {mode !== "demo" ? cur.pdfUrl ? <iframe title={`DACTE ${cur.cte}`} src={cur.pdfUrl} className="aspect-[1/1.414] w-full rounded border" /> : <p className="py-16 text-center text-sm text-muted-foreground">PDF ainda não disponível. {cur.erro}</p> : <div className="aspect-[1/1.414] w-full rounded border bg-background p-4 text-[10px] leading-tight">
                <div className="flex items-start justify-between border-b pb-2"><div><div className="text-sm font-bold">DACTE</div><div>Documento Auxiliar do CT-e</div></div><div className="text-right"><div>Modal Rodoviário</div><div className="font-mono font-semibold">{cur.cte}</div></div></div>
                <div className="mt-2 grid grid-cols-[1fr_auto] gap-2 border-b pb-2">
                  <div><div className="text-muted-foreground">CHAVE DE ACESSO</div><div className="break-all font-mono">{cte?.chave ?? "—"}</div>
                    <div className="mt-1 flex h-8 items-end gap-px">{Array.from({ length: 60 }, (_, i) => <span key={i} className="bg-foreground" style={{ width: ((i * 7) % 3) + 1, height: "100%" }} />)}</div></div>
                  <div className="grid h-16 w-16 grid-cols-6 gap-px border p-0.5">{Array.from({ length: 36 }, (_, i) => <span key={i} className={(i * 13) % 5 < 2 ? "bg-foreground" : ""} />)}</div>
                </div>
                <div className="mt-2 grid grid-cols-2 gap-2"><div><div className="text-muted-foreground">REMETENTE</div>{cte?.remetente}</div><div><div className="text-muted-foreground">DESTINATÁRIO</div>{cte?.destinatario}</div><div><div className="text-muted-foreground">ORIGEM</div>{cte?.origem}</div><div><div className="text-muted-foreground">DESTINO</div>{cte?.destino}</div></div>
                <div className="mt-6 text-center text-muted-foreground">Pré-visualização ilustrativa do modo de demonstração.</div>
              </div>}
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="flex items-center justify-between rounded border p-2"><span className="flex items-center gap-1.5"><QrCode className="h-4 w-4" />QR Code</span><Pill tone={chk(cur.qrCode)[0]}>{chk(cur.qrCode)[1]}</Pill></div>
                <div className="flex items-center justify-between rounded border p-2"><span className="flex items-center gap-1.5"><Barcode className="h-4 w-4" />Código de barras</span><Pill tone={chk(cur.codigoBarras)[0]}>{chk(cur.codigoBarras)[1]}</Pill></div>
              </div>
            </div>
          ) : <div className="flex flex-col items-center gap-2 py-16 text-sm text-muted-foreground"><FileText className="h-8 w-8" />Selecione uma geração para visualizar.</div>}
        </Section>
      </div>
    </PageBody>
  );
}
