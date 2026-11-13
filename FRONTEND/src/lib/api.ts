function defaultApiBase() {
  if (typeof window === "undefined") return "http://127.0.0.1:8000/api";
  const hostname = window.location.hostname || "127.0.0.1";
  return `${window.location.protocol}//${hostname}:8000/api`;
}

export const API_BASE = import.meta.env.VITE_API_BASE_URL || defaultApiBase();

export type StepAction = "click" | "fill" | "wait" | "screenshot";

export interface StepDefinition {
  number: number;
  label: string;
  action: StepAction;
  x: number;
  y: number;
  viewport: { width: number; height: number; dpr: number };
  template?: { path: string; width: number; height: number } | null;
  input_key?: string | null;
  enabled: boolean;
  delay_ms?: number | null;
  loop_point?: boolean;
}

export interface StepCatalog {
  source: string;
  generated_at: string;
  steps: StepDefinition[];
}

export type MapPointKind = "field" | "button" | "tab" | "region" | "other";
export type MapFunctionAction = "click" | "fill" | "wait" | "other";

export interface RodoparMapTab {
  id: string;
  name: string;
  description: string;
  order: number;
  updated_at?: string;
}

export interface RodoparMapSubTab {
  id: string;
  name: string;
  tab: string;
  description: string;
  order: number;
  updated_at?: string;
}

export interface RodoparMapPoint {
  id: string;
  tab: string;
  sub_tab?: string;
  kind: MapPointKind;
  x: number;
  y: number;
  x2?: number | null;
  y2?: number | null;
  viewport: { width: number; height: number; dpr: number };
  description: string;
  updated_at?: string;
}

export interface RodoparFunctionGroup {
  id: string;
  name: string;
  tab: string;
  sub_tab?: string;
  description: string;
  order: number;
  updated_at?: string;
}

export interface RodoparMapFunction {
  id: string;
  name: string;
  tab: string;
  sub_tab?: string;
  group_id: string;
  action: MapFunctionAction;
  point_id: string;
  x: number;
  y: number;
  viewport: { width: number; height: number; dpr: number };
  description: string;
  updated_at?: string;
}

export interface RodoparMapCatalog {
  source: string;
  updated_at: string;
  tabs: RodoparMapTab[];
  sub_tabs: RodoparMapSubTab[];
  points: RodoparMapPoint[];
  function_groups: RodoparFunctionGroup[];
  functions: RodoparMapFunction[];
}

export interface RunSnapshot {
  id: string;
  status: "idle" | "running" | "stopping" | "completed" | "failed" | "cancelled";
  flow: string;
  dry_run: boolean;
  current_step?: number | null;
  message: string;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface ManualSpreadsheetInput {
  filename: string;
  content_base64: string;
}

export interface RunStartPayload {
  flow?: string;
  dry_run: boolean;
  max_steps?: number;
  sample_filial?: string;
  sample_serie?: string;
  sample_documento?: string;
  sample_cte?: string;
  rodopar_replay_overlay_enabled?: boolean;
  manual_ctes?: string;
  manual_spreadsheet?: ManualSpreadsheetInput | null;
  pendentes_sql_days_back?: number;
  pendentes_skip_chamado_missing_comprovante?: boolean;
}

export interface AutomationEvent {
  id: number;
  run_id?: string | null;
  level: "debug" | "info" | "warn" | "error";
  kind: string;
  message: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface BrowserSnapshot {
  url: string;
  image: string;
}

export interface OverlayPoint {
  step: number;
  label: string;
  x: number;
  y: number;
  loopPoint: boolean;
  hasTemplate: boolean;
  shortcut: string;
  ocrText: string;
  hasScrollTarget: boolean;
  hasScrollUpTarget: boolean;
  delayMs: number | null;
  requiresManual: boolean;
  reliableClick: boolean | null;
}

export interface OverlayState {
  status: string;
  captureFile: string;
  currentStep: number | null;
  currentLabel: string;
  points: OverlayPoint[];
  paused: boolean;
  recording: boolean;
}

export interface OverlayCommand {
  type:
    | "pause"
    | "resume"
    | "back"
    | "skip"
    | "capture"
    | "capture_scroll"
    | "capture_scroll_up"
    | "start_recording"
    | "stop_recording"
    | "up"
    | "down"
    | "create"
    | "save"
    | "loop"
    | "cancel"
    | "finish"
    | "clear"
    | "remove"
    | "select"
    | "edit"
    | "reorder";
  label?: string;
  shortcut?: string;
  ocrText?: string;
  delayMs?: number | null;
  manualPause?: boolean;
  reliableClick?: boolean;
  x?: number;
  y?: number;
  screenX?: number;
  screenY?: number;
  step?: number;
  toStep?: number;
}

export interface BrowserState {
  open: boolean;
  connected: boolean;
  pageCount: number;
  urls: string[];
  pid: number | null;
}

export interface FlowDefinition {
  key: string;
  name: string;
  description: string;
  requires_browser: boolean;
  enabled: boolean;
}

export interface EnvEntry {
  key: string;
  value: string;
  source: string;
  group: string;
  isSecret: boolean;
  hasValue: boolean;
}

export interface EnvCatalog {
  total: number;
  groups: Record<string, EnvEntry[]>;
}

export interface ChamadoRow {
  id: string;
  cte: string;
  data: string;
  vlrTotal: number | null;
  aberturaNovelis: string;
  idTarifario: string;
  chamado: string;
  jda: string;
  andamento: string;
  responsavel: string;
  origem: string;
  destino: string;
  cteId: string;
}

export interface ChamadosPayload {
  generatedAt?: string | null;
  sourceFile: string;
  sourceKind?: "fila" | "relatorio";
  total: number;
  queueTotal?: number;
  reportTotal?: number;
  solucionados: number;
  pendentes: number;
  rows: ChamadoRow[];
}

export interface PendentesPlanRow {
  cte: string;
  filial: string;
  serie: string;
  documento: string;
  faltaPdf: boolean;
  faltaXml: boolean;
  faltaComprovante: boolean;
  prontoChamado: boolean;
  pdfFile: string;
  xmlFile: string;
  comprovanteCount: number;
  requiresComprovante: boolean;
  hasGuia: boolean;
  hasComprovanteFile: boolean;
  comprovanteStatus: "ok" | "falta" | "nao_exige";
}

export interface PendentesPlanPayload {
  generatedAt: string;
  sourceFile: string;
  sheetName: string;
  consultados: number;
  total: number;
  faltandoPdfCount: number;
  faltandoXmlCount: number;
  faltandoComprovanteCount: number;
  prontosChamadoCount: number;
  rows: PendentesPlanRow[];
}

export interface AppConfig {
  appName: string;
  environment: string;
  prePasso: {
    rodoparBrowserEnabled: boolean;
    url: string;
    html5Url: string;
    rodoparUrl: string;
    stepDelayMs: number;
  };
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Falha HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getSteps() {
  return apiFetch<StepCatalog>("/steps");
}

export function getFlows() {
  return apiFetch<FlowDefinition[]>("/flows");
}

export function getEnvCatalog() {
  return apiFetch<EnvCatalog>("/config/env");
}

export function getConfig() {
  return apiFetch<AppConfig>("/config");
}

export function getChamados() {
  return apiFetch<ChamadosPayload>("/chamados");
}

export function getPendentesPlan() {
  return apiFetch<PendentesPlanPayload>("/pendentes/plan");
}

export function updateStep(number: number, patch: Partial<StepDefinition>) {
  return apiFetch<StepDefinition>(`/steps/${number}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export function getRodoparMapping() {
  return apiFetch<RodoparMapCatalog>("/mappings/rodopar");
}

export function saveRodoparPoint(point: RodoparMapPoint) {
  return apiFetch<RodoparMapPoint>("/mappings/rodopar/points", {
    method: "PUT",
    body: JSON.stringify(point),
  });
}

export function deleteRodoparPoint(tab: string, pointId: string, subTab = "") {
  const params = new URLSearchParams({ tab, point_id: pointId, sub_tab: subTab });
  return apiFetch<RodoparMapCatalog>(`/mappings/rodopar/points?${params.toString()}`, {
    method: "DELETE",
  });
}

export function saveRodoparTab(tab: RodoparMapTab) {
  return apiFetch<RodoparMapTab>("/mappings/rodopar/tabs", {
    method: "PUT",
    body: JSON.stringify(tab),
  });
}

export function deleteRodoparTab(tabId: string) {
  const params = new URLSearchParams({ tab_id: tabId });
  return apiFetch<RodoparMapCatalog>(`/mappings/rodopar/tabs?${params.toString()}`, {
    method: "DELETE",
  });
}

export function saveRodoparSubTab(subTab: RodoparMapSubTab) {
  return apiFetch<RodoparMapSubTab>("/mappings/rodopar/sub-tabs", {
    method: "PUT",
    body: JSON.stringify(subTab),
  });
}

export function deleteRodoparSubTab(tab: string, subTabId: string) {
  const params = new URLSearchParams({ tab, sub_tab_id: subTabId });
  return apiFetch<RodoparMapCatalog>(`/mappings/rodopar/sub-tabs?${params.toString()}`, {
    method: "DELETE",
  });
}

export function saveRodoparFunctionGroup(group: RodoparFunctionGroup) {
  return apiFetch<RodoparFunctionGroup>("/mappings/rodopar/function-groups", {
    method: "PUT",
    body: JSON.stringify(group),
  });
}

export function deleteRodoparFunctionGroup(groupId: string) {
  const params = new URLSearchParams({ group_id: groupId });
  return apiFetch<RodoparMapCatalog>(
    `/mappings/rodopar/function-groups?${params.toString()}`,
    { method: "DELETE" },
  );
}

export function saveRodoparFunction(mapFunction: RodoparMapFunction) {
  return apiFetch<RodoparMapFunction>("/mappings/rodopar/functions", {
    method: "PUT",
    body: JSON.stringify(mapFunction),
  });
}

export function deleteRodoparFunction(functionId: string) {
  const params = new URLSearchParams({ function_id: functionId });
  return apiFetch<RodoparMapCatalog>(`/mappings/rodopar/functions?${params.toString()}`, {
    method: "DELETE",
  });
}

export function getCurrentRun() {
  return apiFetch<RunSnapshot>("/runs/current");
}

export function startRun(payload: RunStartPayload) {
  return apiFetch<RunSnapshot>("/runs/start", {
    method: "POST",
    body: JSON.stringify({ flow: payload.flow ?? "pendentes", ...payload }),
  });
}

export function stopRun() {
  return apiFetch<RunSnapshot>("/runs/stop", { method: "POST" });
}

export function importCaptureFile(path: string, content: unknown) {
  return apiFetch<{ status: string; path: string; totalPoints: string }>("/capture-files/import", {
    method: "POST",
    body: JSON.stringify({ path, content }),
  });
}

export function confirmManualLogin(runId: string, key = "rodopar-login") {
  return apiFetch<{ status: string; run_id: string; key: string }>(
    `/runs/${runId}/manual-confirmation`,
    {
      method: "POST",
      body: JSON.stringify({ key }),
    },
  );
}

export function getOverlayState(runId: string) {
  return apiFetch<OverlayState>(`/runs/${runId}/overlay/state`);
}

export function sendOverlayCommand(runId: string, command: OverlayCommand) {
  return apiFetch<{ status: string; run_id: string }>(`/runs/${runId}/overlay/command`, {
    method: "POST",
    body: JSON.stringify(command),
  });
}

export function openBrowser(url?: string) {
  return apiFetch<BrowserSnapshot>("/browser/open", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

export function getBrowserScreenshot() {
  return apiFetch<BrowserSnapshot>("/browser/screenshot");
}

export function getBrowserState() {
  return apiFetch<BrowserState>("/browser/state");
}

export function clickBrowser(x: number, y: number) {
  return apiFetch<BrowserSnapshot>("/browser/click", {
    method: "POST",
    body: JSON.stringify({ x, y }),
  });
}

export function closeBrowser() {
  return apiFetch<{ status: string }>("/browser/close", { method: "POST" });
}

export function browserSiteUrl(path = "") {
  const target = path.trim();
  if (!target) return `${API_BASE}/browser/site/`;
  try {
    const parsed = new URL(target);
    if (parsed.origin === "https://www.cte.fazenda.gov.br") {
      return `${API_BASE}/browser/sefaz${parsed.pathname}${parsed.search}${parsed.hash}`;
    }
    if (parsed.origin !== "https://webcloud16.datapardc.com") return parsed.href;
    return `${API_BASE}/browser/site${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    const normalizedPath = target.replace(/^\/+/, "");
    return `${API_BASE}/browser/site/${normalizedPath}`;
  }
}
