import type { AutomationSchedule, RunStatus, ScheduleList } from "./types";

export const widgetSnapshotKey = "cargo-hub.status-widget.snapshot.v1";
export const widgetStaleAfter = 20_000;
export type WidgetMotion =
  | "download"
  | "generate"
  | "verify"
  | "validate"
  | "send"
  | "error"
  | "success"
  | "connect"
  | "wait"
  | "stop"
  | "locked";
export interface WidgetSnapshot {
  schema: 1;
  updatedAt: number;
  connection: "connected" | "connecting" | "offline" | "login_required" | "demo";
  state: RunStatus["state"];
  activity: string;
  activityKind?: WidgetMotion;
  detail: string;
  cte: string | null;
  done: number;
  total: number;
  next: { name: string; at: string; attempt: number } | null;
  failure: { name: string; at: string | null; message: string } | null;
  activeSchedules: number;
  schedulerRunning: boolean | null;
}

const activities = {
  consulta: "Consultando CT-es",
  pdf: "Gerando PDF",
  xml: "Baixando XML",
  comprovantes: "Buscando comprovantes",
  chamados: "Abrindo chamados",
};
const nodeActivities: Record<string, string> = {
  pdf: "Gerando PDF",
  xml: "Baixando XML",
  tickets: "Abrindo chamados",
  sql: "Consultando SQL",
  novelis_report: "Consultando relatório Novelis",
  compare: "Comparando relatório",
  files: "Verificando arquivos",
  proof: "Buscando comprovantes",
  tariffs: "Atualizando tarifário",
  generate_report: "Gerando relatório",
};

export function makeWidgetSnapshot({
  run,
  schedules,
  connection,
  now = Date.now(),
}: {
  run: RunStatus | undefined;
  schedules: ScheduleList | undefined;
  connection: WidgetSnapshot["connection"];
  now?: number;
}): WidgetSnapshot {
  const active = (schedules?.schedules ?? []).filter((value) => value.enabled);
  const next = active
    .filter((value) => value.next_run_at && Number.isFinite(Date.parse(value.next_run_at)))
    .sort((a, b) => Date.parse(a.next_run_at!) - Date.parse(b.next_run_at!))[0];
  const last = (schedules?.schedules ?? [])
    .filter((value) => value.last_run)
    .sort((a, b) => lastTime(b) - lastTime(a))[0];
  const node = run?.workflow?.nodes.find((value) => value.id === run.workflow?.current_node_id);
  const stage = run?.stages.find(
    (value) => value.state === "executando" || value.state === "falhou",
  );
  const currentRunTime = Date.parse(run?.finalizadoEm ?? run?.iniciadoEm ?? "") || 0;
  const detail = (node?.detail || stage?.atividade || stage?.detalhe || "").slice(0, 220);
  const failed =
    last?.last_run &&
    ["failed", "interrupted"].includes(last.last_run.state) &&
    lastTime(last) >= currentRunTime;
  return {
    schema: 1,
    updatedAt: now,
    connection,
    state: run?.state ?? "aguardando",
    activity:
      (node && nodeActivities[node.kind]) ||
      node?.label ||
      (run?.etapaAtual && activities[run.etapaAtual]) ||
      "Automação em execução",
    activityKind: activityMotion(node?.kind ?? run?.etapaAtual ?? "", detail),
    detail,
    cte: run?.cteAtual ?? null,
    done: run?.workflow?.completed ?? run?.processados ?? 0,
    total: run?.workflow?.total ?? run?.total ?? 0,
    next: next ? { name: next.name, at: next.next_run_at!, attempt: next.next_attempt ?? 0 } : null,
    failure: failed
      ? {
          name: last.name,
          at: last.last_run!.finished_at ?? last.last_run!.started_at,
          message: last.last_run!.message.slice(0, 220),
        }
      : null,
    activeSchedules: active.length,
    schedulerRunning: schedules?.running ?? null,
  };
}

function activityMotion(kind: string, detail: string): WidgetMotion {
  if (/valid|confer|compar|decodific/i.test(detail)) return "validate";
  if (/verific|chec/i.test(detail)) return "verify";
  if (["pdf", "generate_report"].includes(kind)) return "generate";
  if (["xml", "novelis_report", "tariffs"].includes(kind)) return "download";
  if (kind === "compare") return "validate";
  if (["tickets", "chamados"].includes(kind)) return "send";
  return "verify";
}

export function widgetMotion(value: WidgetSnapshot | null, now = Date.now()): WidgetMotion {
  const status = widgetStatus(value, now);
  if (!status.connected) {
    if (value?.connection === "login_required") return "locked";
    return value?.connection === "demo" ? "wait" : "connect";
  }
  if (status.tone === "error") return "error";
  if (value?.state === "parando" || value?.state === "cancelada") return "stop";
  if (status.tone === "warning") return "wait";
  if (value?.state === "concluida") return "success";
  if (value?.state !== "executando") return "wait";
  if (value.activityKind) return value.activityKind;
  // Snapshots written by an earlier application version still remain readable.
  const text = `${value.activity} ${value.detail}`;
  if (/valid|confer|compar|decodific/i.test(text)) return "validate";
  if (/baix|download/i.test(text)) return "download";
  if (/ger|pdf/i.test(text)) return "generate";
  return "verify";
}

function lastTime(value: AutomationSchedule) {
  return Date.parse(value.last_run?.finished_at ?? value.last_run?.started_at ?? "") || 0;
}

export function readWidgetSnapshot(): WidgetSnapshot | null {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(widgetSnapshotKey) ?? "null");
    if (!value || typeof value !== "object") return null;
    const item = value as WidgetSnapshot;
    return item.schema === 1 &&
      Number.isFinite(item.updatedAt) &&
      typeof item.activity === "string" &&
      typeof item.activeSchedules === "number"
      ? item
      : null;
  } catch {
    return null;
  }
}

export function widgetStatus(value: WidgetSnapshot | null, now = Date.now()) {
  if (!value || now - value.updatedAt > widgetStaleAfter)
    return { label: "Aguardando atualização", tone: "warning", connected: false } as const;
  if (value.connection === "offline")
    return { label: "Reconectando", tone: "warning", connected: false } as const;
  if (value.connection === "connecting")
    return { label: "Conectando", tone: "neutral", connected: false } as const;
  if (value.connection === "login_required")
    return { label: "Entre no Cargo Hub", tone: "neutral", connected: false } as const;
  if (value.connection === "demo")
    return { label: "Modo demonstração", tone: "neutral", connected: false } as const;
  if (value.state === "executando")
    return { label: value.activity, tone: "running", connected: true } as const;
  if (value.state === "parando")
    return { label: "Interrompendo execução", tone: "warning", connected: true } as const;
  if (value.state === "falhou")
    return { label: "Falha na execução", tone: "error", connected: true } as const;
  if (value.failure)
    return { label: "Última rotina com falha", tone: "error", connected: true } as const;
  if (value.schedulerRunning === false)
    return { label: "Agendador inativo", tone: "warning", connected: true } as const;
  if (value.state === "cancelada")
    return { label: "Execução cancelada", tone: "neutral", connected: true } as const;
  if (value.state === "concluida")
    return { label: "Execução concluída", tone: "success", connected: true } as const;
  return { label: "Aguardando agendamento", tone: "neutral", connected: true } as const;
}
