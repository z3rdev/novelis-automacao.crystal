import { Info, Layers } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { RunStatus, StageProgress } from "@/services";
import { Pill, StagePill, stageLabel } from "./status";
import { cn } from "@/lib/utils";
import "./run-panel.css";

export function StageCard({ stage, parallel = false }: { stage: StageProgress; parallel?: boolean }) {
  const pct = stage.total ? Math.min(100, Math.round((stage.done / stage.total) * 100)) : stage.state === "concluida" ? 100 : 0;
  const available = stage.state === "concluida" && !!stage.detalhe && stage.total === 0;
  const caption = available ? stage.reaproveitados ? `${stage.reaproveitados} disponíveis` : "Sem pendências" : stage.id === "consulta" && stage.state === "concluida" ? "Lista atualizada" : `${stage.done} de ${stage.total}`;
  return (
    <div data-stage={stage.id} className={cn("run-stage-card rounded-md border bg-card p-3", stage.state === "executando" && "border-info bg-info/5", stage.state === "parando" && "border-warning bg-warning/5", stage.state === "ignorada" && "opacity-65")}>
      <div className="flex items-start justify-between gap-2">
        <span className="min-w-0 text-sm font-semibold">{stageLabel[stage.id]}</span>
        {stage.detalhe && <Tooltip><TooltipTrigger asChild><button type="button" aria-label={`Detalhes de ${stageLabel[stage.id]}`} className="shrink-0 rounded text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"><Info className="h-4 w-4" /></button></TooltipTrigger><TooltipContent className="max-w-72 break-words leading-relaxed" side="top">{stage.detalhe}</TooltipContent></Tooltip>}
      </div>
      <div>{available ? <Pill tone="success">Já disponíveis</Pill> : <StagePill s={stage.state} />}</div>
      {stage.atual && ["executando", "parando"].includes(stage.state) && <div className="break-words font-mono text-xs text-muted-foreground">{stage.atual}</div>}
      <div className="mt-auto space-y-2">
        <Progress value={pct} className="h-1.5" />
        <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-2 text-xs text-muted-foreground tabular-nums"><span>{caption}</span><span>{pct}%</span></div>
      </div>
      {parallel && stage.state === "executando" && <div className="text-[11px] text-info">{stage.id === "pdf" ? "Um CT-e por vez" : "Em paralelo ao PDF"}</div>}
    </div>
  );
}

export function StagesView({ run }: { run: RunStatus }) {
  const by = (id: StageProgress["id"]): StageProgress => run.stages.find((stage) => stage.id === id) ?? { id, state: "aguardando", done: 0, total: 0 };
  const parallel = by("pdf").state !== "ignorada" && by("xml").state !== "ignorada" && [by("pdf"), by("xml")].some((stage) => ["aguardando", "executando"].includes(stage.state));
  return (
    <div className="run-stages">
      <div className="run-stages-grid">
        <div className="run-stage-consulta"><StageCard stage={by("consulta")} /></div>
        <div className="run-stage-documents min-w-0 rounded-md border border-dashed bg-muted/20 p-2">
          <div className="mb-2 flex flex-wrap items-center gap-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground"><Layers className="h-3.5 w-3.5 shrink-0" />{parallel ? "Documentos · PDF e XML simultâneos" : "Documentos"}</div>
          <div className="run-documents-grid"><StageCard stage={by("pdf")} parallel={parallel} /><StageCard stage={by("xml")} parallel={parallel} /></div>
        </div>
        <StageCard stage={by("comprovantes")} />
        <StageCard stage={by("chamados")} />
      </div>
    </div>
  );
}
