export interface ReportTicket {
  cte: string;
  numero: string;
  link: string;
  origem: string;
  destino: string;
  ton: string;
  id_tarifa: string;
  valor: number | null;
  frete: number | null;
  conferencia: string;
  confirmado_em: string;
  operator?: string;
  computer?: string;
  run_id?: string;
}
export interface ExecutionReport {
  id: string;
  kind?: "daily";
  report_date?: string;
  operators?: string[];
  computers?: string[];
  run_count?: number;
  operator: string;
  computer: string;
  flow: string;
  status: "completed" | "failed" | "cancelled";
  started_at: string;
  finished_at: string;
  generated_at: string;
  opened_count: number;
  existing_count: number;
  share_status: "pending" | "shared";
  share_message: string;
  opened?: ReportTicket[];
  existing?: ReportTicket[];
}
export interface ExecutionReportPage {
  rows: ExecutionReport[];
  total: number;
  page: number;
  page_size: number;
}
export interface ExecutionReportApi {
  listExecutionReports(page: number): Promise<ExecutionReportPage>;
  getExecutionReport(id: string): Promise<ExecutionReport>;
  downloadExecutionReport(id: string): Promise<Blob>;
  syncExecutionReports(): Promise<void>;
}
