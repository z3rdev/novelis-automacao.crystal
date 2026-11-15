import { CheckCircle2, CircleDashed, Loader2, MinusCircle, XCircle, AlertTriangle, Clock, Ban, PauseCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { DocStatus, RunState, StageState, StageId, FlowId } from "@/services/types";

export type Tone = "success" | "warning" | "error" | "info" | "neutral";
const toneCls: Record<Tone, string> = {
  success: "bg-success/12 text-success border-success/30",
  warning: "bg-warning/20 text-warning-foreground border-warning/50",
  error: "bg-destructive/10 text-destructive border-destructive/30",
  info: "bg-info/10 text-info border-info/30",
  neutral: "bg-muted text-muted-foreground border-border",
};

export function Pill({ tone, icon: Icon, children, className }: { tone: Tone; icon?: React.ComponentType<{ className?: string }>; children: React.ReactNode; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1 whitespace-nowrap rounded border px-1.5 py-0.5 text-xs font-medium", toneCls[tone], className)}>
      {Icon && <Icon className={cn("h-3.5 w-3.5", tone === "info" && Icon === Loader2 && "animate-spin")} />}
      {children}
    </span>
  );
}

export function DocPill({ s }: { s: DocStatus }) {
  if (s === "disponivel") return <Pill tone="success" icon={CheckCircle2}>Disponível</Pill>;
  if (s === "faltando") return <Pill tone="warning" icon={AlertTriangle}>Faltando</Pill>;
  return <Pill tone="neutral" icon={MinusCircle}>Não exige</Pill>;
}

export const runLabel: Record<RunState, string> = { aguardando: "Aguardando", executando: "Executando", parando: "Parando", concluida: "Concluída", falhou: "Falhou", cancelada: "Cancelada" };
export function RunPill({ s }: { s: RunState }) {
  const m: Record<RunState, [Tone, React.ComponentType<{ className?: string }>]> = {
    aguardando: ["neutral", Clock], executando: ["info", Loader2], parando: ["warning", PauseCircle],
    concluida: ["success", CheckCircle2], falhou: ["error", XCircle], cancelada: ["neutral", Ban],
  };
  const [t, i] = m[s];
  return <Pill tone={t} icon={i}>{runLabel[s]}</Pill>;
}

export function StagePill({ s }: { s: StageState }) {
  const m: Record<StageState, [Tone, React.ComponentType<{ className?: string }>, string]> = {
    aguardando: ["neutral", Clock, "Aguardando"], executando: ["info", Loader2, "Executando"], concluida: ["success", CheckCircle2, "Concluída"],
    falhou: ["error", XCircle, "Falhou"], ignorada: ["neutral", CircleDashed, "Fora do fluxo"],
    parando: ["warning", PauseCircle, "Parando"], cancelada: ["neutral", Ban, "Cancelada"],
  };
  const [t, i, l] = m[s];
  return <Pill tone={t} icon={i}>{l}</Pill>;
}

export const stageLabel: Record<StageId, string> = { consulta: "Consulta", pdf: "PDF (DACTE)", xml: "XML (SEFAZ)", comprovantes: "Comprovantes", chamados: "Chamados" };
export const flowLabel: Record<FlowId, string> = {
  personalizado: "Fluxo personalizado",
  somente_comprovantes: "Somente buscar comprovantes", buscar_chamados: "Atualizar relatório de chamados Novelis",
  consulta: "Somente consulta de pendências",
  completo: "Fluxo completo (consulta → chamados)", documentos: "Somente documentos (sem chamados)",
  somente_pdf: "Somente geração de PDF", somente_xml: "Somente busca de XML", somente_chamados: "Somente chamados Novelis",
};
