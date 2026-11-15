export type DiagnosticState =
  "queued" | "running" | "completed" | "failed" | "expired" | "timed_out";
export type CheckState = "ok" | "warning" | "failed" | "not_tested" | "unavailable";
export interface DiagnosticAgent {
  device_id: string;
  machine_id: string;
  computer_name: string;
  version: string;
  installation_kind: string;
  protocol: number;
  last_seen: string;
  online: boolean;
  current_request: string | null;
}
export interface DiagnosticEvent {
  time: string | null;
  severity: string;
  source: string;
  message: string;
  details: Record<string, unknown>;
}
export interface DiagnosticCheck {
  id: string;
  title: string;
  status: CheckState;
  message: string;
  source: string;
  checked_at: string;
  details: Record<string, unknown>;
}
export interface DiagnosticRun {
  id: string;
  flow: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  message: string;
  dry_run: boolean;
  events: DiagnosticEvent[];
  events_truncated: boolean;
}
export interface DiagnosticSummary {
  runs: number;
  failed_runs: number;
  cancelled_runs: number;
  http_events: number;
  confirmed_tickets: number;
  issues: number;
}
export interface DiagnosticReport {
  schema_version: number;
  checked_at: string;
  complete: boolean;
  incomplete_reason?: string;
  device: { computer_name: string; windows_user: string; version: string };
  scope: { max_runs: number; days_back: number };
  summary: DiagnosticSummary;
  checks: DiagnosticCheck[];
  runs: DiagnosticRun[];
  http: DiagnosticEvent[];
  events_truncated?: boolean;
  http_truncated?: boolean;
  duration_seconds: number;
  limitations: string[];
}
export interface DiagnosticRequest {
  id: string;
  device_id: string;
  computer_name: string;
  requested_by: string;
  requested_at: string;
  expires_at: string;
  state: DiagnosticState;
  options: { max_runs: number; days_back: number };
  started_at: string | null;
  finished_at: string | null;
  error_code: string;
  summary?: DiagnosticSummary | null;
  result?: DiagnosticReport | null;
}
export interface RemoteDiagnosticsApi {
  getDiagnosticAgents(): Promise<{ agents: DiagnosticAgent[] }>;
  listDiagnosticRequests(): Promise<{ requests: DiagnosticRequest[] }>;
  requestDiagnostic(
    deviceId: string,
    maxRuns: number,
    daysBack: number,
  ): Promise<DiagnosticRequest>;
  getDiagnosticRequest(id: string): Promise<DiagnosticRequest>;
}
export const diagnosticStateLabels: Record<DiagnosticState, string> = {
  queued: "Na fila",
  running: "Coletando",
  completed: "Concluído",
  failed: "Falhou",
  expired: "Sem resposta",
  timed_out: "Tempo esgotado",
};
export const diagnosticCheckLabels: Record<CheckState, string> = {
  ok: "Verificado",
  warning: "Atenção",
  failed: "Falhou",
  not_tested: "Não testado",
  unavailable: "Indisponível",
};
