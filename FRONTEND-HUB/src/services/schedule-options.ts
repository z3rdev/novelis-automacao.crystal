import type { ScheduleInput } from "./operator-features";

export const weekdayNames = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];
export const fullWeekdays = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"];
export const scheduleFlows = {
  consulta: "Consulta e verificação",
  somente_pdf: "Baixar PDFs",
  somente_xml: "Baixar XMLs",
  somente_comprovantes: "Buscar comprovantes",
  buscar_chamados: "Atualizar chamados Novelis (relatório)",
  completo: "Fluxo completo",
  personalizado: "Fluxo personalizado",
};
export const emptySchedule = (): ScheduleInput => ({
  name: "",
  time: "08:00",
  weekdays: [0, 1, 2, 3, 4, 5, 6],
  flow: "consulta",
  days_back: 0,
  enabled: true,
  runs_per_day: 1,
  interval_minutes: 60,
  max_retries: 0,
  retry_interval_minutes: 5,
});

export function scheduleDraft(value: ScheduleInput): ScheduleInput {
  return {
    ...emptySchedule(),
    ...value,
    weekdays: [...value.weekdays],
    workflow: value.workflow ? structuredClone(value.workflow) : null,
  };
}

export function weekdaySummary(days: number[]) {
  if (days.length === 7) return "Todos os dias";
  if (days.length === 5 && [0, 1, 2, 3, 4].every((day) => days.includes(day))) return "Dias úteis";
  return days.map((day) => weekdayNames[day]).join(", ");
}

export const scheduleStates: Record<string, string> = {
  waiting: "Aguardando nova tentativa",
  starting: "Iniciando",
  running: "Em execução",
  completed: "Concluída",
  failed: "Falhou",
  cancelled: "Cancelada",
  interrupted: "Interrompida",
};

export function scheduleDate(iso: string, now = new Date()) {
  const date = new Date(iso);
  const day = (value: Date) => Date.UTC(value.getFullYear(), value.getMonth(), value.getDate());
  const distance = Math.round((day(date) - day(now)) / 86400000);
  const label =
    distance === 0
      ? "Hoje"
      : distance === 1
        ? "Amanhã"
        : distance === -1
          ? "Ontem"
          : date.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
  return `${label}, ${date.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`;
}

export function scheduleRemaining(iso: string, now = Date.now()) {
  const minutes = Math.ceil((new Date(iso).getTime() - now) / 60000);
  if (minutes <= 0) return "Aguardando a vez";
  const hours = Math.floor(minutes / 60);
  return `em ${hours ? `${hours} h ` : ""}${minutes % 60 || !hours ? `${minutes % 60} min` : ""}`.trim();
}
