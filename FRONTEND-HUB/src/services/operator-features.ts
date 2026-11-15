import type { ScheduledWorkflow } from "./scheduled-workflow";

export interface HubNotification {
  id: string;
  title: string;
  body: string;
  severity: "info" | "warning" | "critical";
  author: string;
  created_at: string;
  expires_at: string | null;
  archived_at: string | null;
  read_at?: string | null;
}

export interface NotificationInput {
  title: string;
  body: string;
  severity: HubNotification["severity"];
  expires_at: string | null;
}

export interface ScheduleInput {
  name: string;
  time: string;
  weekdays: number[];
  flow:
    | "consulta"
    | "somente_pdf"
    | "somente_xml"
    | "somente_comprovantes"
    | "buscar_chamados"
    | "completo"
    | "personalizado";
  workflow?: ScheduledWorkflow | null;
  days_back: number;
  enabled: boolean;
  runs_per_day?: number;
  interval_minutes?: number;
  max_retries?: number;
  retry_interval_minutes?: number;
}

export interface AutomationSchedule extends ScheduleInput {
  id: string;
  revision: number;
  operator_name: string;
  activated_at: string;
  next_run_at: string | null;
  next_slot?: number | null;
  next_attempt?: number | null;
  last_run: {
    local_date: string;
    state: string;
    run_id: string | null;
    started_at: string;
    finished_at: string | null;
    message: string;
    slot?: number;
    attempt?: number;
  } | null;
}

export interface ScheduleList {
  schedules: AutomationSchedule[];
  device: string;
  local_time: string;
  running?: boolean;
}

export interface ScheduleAttempt {
  local_date: string;
  slot: number;
  attempt: number;
  due_at: string;
  state: string;
  run_id: string | null;
  started_at: string | null;
  finished_at: string | null;
  message: string;
}
export interface ScheduleHistory {
  rows: ScheduleAttempt[];
  total: number;
  page: number;
  page_size: number;
}
