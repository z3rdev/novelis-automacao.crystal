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
  flow: "consulta" | "somente_pdf" | "completo";
  days_back: number;
  enabled: boolean;
}

export interface AutomationSchedule extends ScheduleInput {
  id: string;
  revision: number;
  operator_name: string;
  activated_at: string;
  next_run_at: string | null;
  last_run: {
    local_date: string;
    state: string;
    run_id: string | null;
    started_at: string;
    finished_at: string | null;
    message: string;
  } | null;
}

export interface ScheduleList {
  schedules: AutomationSchedule[];
  device: string;
  local_time: string;
}
