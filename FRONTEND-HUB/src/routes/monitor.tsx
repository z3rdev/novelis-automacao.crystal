import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { ExternalLink, Globe, Pause, Play, Search, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { PageBody, Section } from "@/components/app/page";
import { Pill, type Tone } from "@/components/app/status";
import { useRun, RunSummary, StagesView } from "@/components/app/run-panel";
import { useApi, type LogEntry, type Severity } from "@/services";
import { fmtTime } from "@/lib/format";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/monitor")({
  head: () => ({ meta: [
    { title: "Monitor da automação · Automação Novelis" },
    { name: "description", content: "Acompanhe o navegador da automação e os eventos em tempo real." },
    { property: "og:title", content: "Monitor da automação · Automação Novelis" },
    { property: "og:description", content: "Acompanhe o navegador da automação e os eventos em tempo real." },
  ] }),
  component: Monitor,
});

const sev: Record<Severity, [Tone, string]> = { info: ["info", "Info"], sucesso: ["success", "Sucesso"], aviso: ["warning", "Aviso"], erro: ["error", "Erro"], debug: ["neutral", "Debug"] };

function Monitor() {
  const { api, mode, baseUrl } = useApi();
  const run = useRun();
  const frame = useQuery({ queryKey: ["frame", mode, baseUrl], queryFn: () => api.getBrowserFrame(), refetchInterval: 1500, retry: 0 });
  const [paused, setPaused] = useState(false);
  const logsQ = useQuery({ queryKey: ["logs", mode, baseUrl], queryFn: () => api.listLogs(), refetchInterval: paused ? false : 1000, retry: 0 });
  const [clearedAt, setClearedAt] = useState(0);
  const [busca, setBusca] = useState("");
  const [sevs, setSevs] = useState<string[]>(["info", "sucesso", "aviso", "erro"]);
  const [open, setOpen] = useState<string | null>(null);
  const logBoxRef = useRef<HTMLDivElement>(null);
  const logs = useMemo(() => (logsQ.data ?? []).filter((l: LogEntry) => Number(l.id) > clearedAt && sevs.includes(l.severity) && (!busca || `${l.message} ${l.details ?? ""} ${l.source}`.toLowerCase().includes(busca.toLowerCase()))), [logsQ.data, clearedAt, sevs, busca]);
  useEffect(() => { if (!paused && logBoxRef.current) logBoxRef.current.scrollTop = logBoxRef.current.scrollHeight; }, [logs.length, paused]);
  const f = frame.data;
  const focus = useMutation({ mutationFn: () => api.focusBrowser(), onError: (error: Error) => toast.error(error.message) });
  const lastXml = logsQ.data?.filter((entry) => entry.source.startsWith("xml_sefaz.") && entry.time >= (run.data?.iniciadoEm ?? "")).at(-1);
  const waitingCaptcha = run.data?.state === "executando" && lastXml?.source === "xml_sefaz.captcha";
  return (
    <PageBody>
      <div className="grid gap-4 xl:grid-cols-2">
        <Section title="Navegador da automação" actions={mode !== "demo" && f?.ativo ? <Button variant="outline" size="sm" onClick={() => focus.mutate()} disabled={focus.isPending}><ExternalLink />Mostrar navegador</Button> : undefined}>
          {waitingCaptcha && <div role="status" className="mb-3 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950">SEFAZ aguardando confirmação: clique em <strong>Mostrar navegador</strong> e resolva o hCaptcha. Depois a consulta e o download continuam automaticamente.</div>}
          <div className="overflow-hidden rounded-md border">
            <div className="flex items-center gap-2 border-b bg-muted px-3 py-1.5 text-xs"><Globe className="h-3.5 w-3.5" /><span className="truncate font-mono">{f?.url ?? "—"}</span>{f?.ativo && <Pill tone="info" className="ml-auto">Ao vivo</Pill>}</div>
            <div className="grid aspect-video place-items-center bg-background p-6 text-center">
              {mode !== "demo" && f?.ativo ? f.screenshot ? <img src={f.screenshot} alt="Captura atual do navegador da automação neste computador" className="w-full" /> : <p className="text-sm text-muted-foreground">{f.acao}</p> : f?.ativo ? (
                <div className="w-full max-w-sm space-y-2 text-left text-sm"><div className="font-semibold">{f.titulo}</div>{["CT-e", "ID tarifário", "Valor", "Anexos"].map((l, i) => <div key={l}><div className="text-xs text-muted-foreground">{l}</div><div className={cn("h-7 rounded border", i === 1 && "border-info ring-2 ring-info/30")} /></div>)}<div className="text-xs text-info">{f.acao}</div></div>
              ) : run.data && run.data.state === "executando" ? (
                <div className="w-full space-y-3 text-left"><div className="text-sm text-muted-foreground">Sem navegador nesta etapa — andamento:</div><RunSummary run={run.data} /></div>
              ) : <div className="text-sm text-muted-foreground">{f?.acao ?? "Carregando…"}</div>}
            </div>
          </div>
        </Section>
        <Section title="Etapas">{run.data ? <StagesView run={run.data} /> : <p className="text-sm text-muted-foreground">—</p>}</Section>
      </div>
      <Section title={`Eventos e logs (${logs.length})`} actions={<>
        <div className="relative"><Search className="absolute left-2 top-2 h-4 w-4 text-muted-foreground" /><Input className="h-8 w-56 pl-7 text-xs" placeholder="Buscar mensagem ou detalhe…" value={busca} onChange={(e) => setBusca(e.target.value)} /></div>
        <ToggleGroup type="multiple" size="sm" variant="outline" value={sevs} onValueChange={setSevs}>{Object.entries(sev).map(([k, v]) => <ToggleGroupItem key={k} value={k} className="text-xs">{v[1]}</ToggleGroupItem>)}</ToggleGroup>
        <Button size="sm" variant="outline" onClick={() => setPaused((p) => !p)}>{paused ? <><Play />Retomar</> : <><Pause />Pausar</>}</Button>
        <Button size="sm" variant="ghost" onClick={() => setClearedAt(Number(logsQ.data?.at(-1)?.id ?? 0))}><Trash2 />Limpar</Button>
      </>}>
        <div ref={logBoxRef} className="max-h-[50vh] overflow-auto rounded border font-mono text-xs">
          <table className="w-full">
            <thead className="sticky top-0 bg-muted text-left"><tr><th className="w-24 px-2 py-1.5">Horário</th><th className="w-24 px-2">Severidade</th><th className="w-28 px-2">Origem</th><th className="px-2">Mensagem</th></tr></thead>
            <tbody>
              {logs.map((l) => (<Fragment key={l.id}>
                <tr key={l.id} className={cn("cursor-pointer border-t hover:bg-muted/50", l.severity === "erro" && "bg-destructive/5")} onClick={() => setOpen(open === l.id ? null : l.id)}>
                  <td className="px-2 py-1 tabular-nums">{fmtTime(l.time)}</td><td className="px-2"><Pill tone={sev[l.severity][0]}>{sev[l.severity][1]}</Pill></td><td className="px-2 text-muted-foreground">{l.source}</td><td className="px-2 font-sans">{l.message}{l.details && <span className="ml-1 text-muted-foreground">{open === l.id ? "▾" : "▸"}</span>}</td>
                </tr>
                {open === l.id && l.details && <tr key={l.id + "d"}><td colSpan={4} className="bg-muted/40 px-4 py-2 whitespace-pre-wrap">{l.details}</td></tr>}
              </Fragment>))}
              {!logs.length && <tr><td colSpan={4} className="py-8 text-center text-muted-foreground">Nenhum evento.</td></tr>}
            </tbody>
          </table>
        </div>
      </Section>
    </PageBody>
  );
}
