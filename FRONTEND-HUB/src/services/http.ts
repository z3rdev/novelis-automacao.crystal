import type { AutomationApi, DacteJob } from "./types";
import { createChatApi } from "./chat-http";

export function createHttpApi(baseUrl: string): AutomationApi {
  const sessionKey = `novelis.operator-session:${baseUrl.replace(/\/$/, "")}`;
  const token = () => typeof window === "undefined" ? null : sessionStorage.getItem(sessionKey);
  const req = async <T,>(path: string, init?: RequestInit): Promise<T> => {
    const attempts = !init?.method || init.method === "GET" ? 2 : 1;
    for (let attempt = 0; attempt < attempts; attempt++) {
      try {
        const res = await fetch(`${baseUrl.replace(/\/$/, "")}${path}`, {
          ...init,
          signal: init?.signal ?? AbortSignal.timeout(30000),
          headers: { "Content-Type": "application/json", ...(token() ? { "X-Operator-Session": token()! } : {}), ...(init?.headers ?? {}) },
        });
        if (!res.ok) {
          const error = await res.json().catch(() => null);
          throw new Error(typeof error?.detail === "string" ? error.detail : `Backend respondeu ${res.status} em ${path}`);
        }
        return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
      } catch (error) {
        const name = error && typeof error === "object" && "name" in error ? String(error.name) : "";
        const timeout = ["TimeoutError", "AbortError"].includes(name);
        const network = name === "TypeError";
        if ((timeout || network) && !init?.signal?.aborted && attempt + 1 < attempts) continue;
        if (timeout) throw new Error("A consulta ao backend demorou além do esperado. Verifique a conexão com as pastas de rede e tente novamente.");
        if (network) throw new Error("A conexão com o backend local foi interrompida. Tentando reconectar nas próximas consultas.");
        throw error;
      }
    }
    throw new Error("Não foi possível concluir a consulta ao backend.");
  };
  const post = <T,>(p: string, body?: unknown) => req<T>(p, { method: "POST", body: JSON.stringify(body ?? {}) });
  const put = <T,>(p: string, body: unknown) => req<T>(p, { method: "PUT", body: JSON.stringify(body) });
  return {
    ...createChatApi(req, async (path) => {
      const response = await fetch(`${baseUrl.replace(/\/$/, "")}${path}`, {
        headers: token() ? { "X-Operator-Session": token()! } : {}, signal: AbortSignal.timeout(90_000),
      });
      if (!response.ok) throw new Error("Não foi possível baixar o documento desta conversa.");
      return response.blob();
    }),
    getDiagnosticAgents: () => req("/developer/diagnostics/agents"),
    listDiagnosticRequests: () => req("/developer/diagnostics"),
    requestDiagnostic: (deviceId, maxRuns, daysBack) => post("/developer/diagnostics", { device_id: deviceId, options: { max_runs: maxRuns, days_back: daysBack } }),
    getDiagnosticRequest: (id) => req(`/developer/diagnostics/${encodeURIComponent(id)}`),
    listExecutionReports: (page) => req(`/execution-reports?page=${page}`),
    getExecutionReport: (id) => req(`/execution-reports/${encodeURIComponent(id)}`),
    async downloadExecutionReport(id) {
      const response = await fetch(`${baseUrl.replace(/\/$/, "")}/execution-reports/${encodeURIComponent(id)}/file`, {
        headers: token() ? { "X-Operator-Session": token()! } : {}, signal: AbortSignal.timeout(90000),
      });
      if (!response.ok) throw new Error("Não foi possível baixar o Excel. Verifique a conexão e tente novamente.");
      return response.blob();
    },
    syncExecutionReports: () => post("/execution-reports/sync"),
    listTariffs: (query) => req(`/tariffs?${new URLSearchParams(Object.entries(query).map(([key,value])=>[key,String(value)]))}`),
    tariffCities: (search) => req(`/tariffs/cities?search=${encodeURIComponent(search)}`),
    getTariffSync: () => req("/tariffs/sync"),
    refreshTariffs: () => post("/tariffs/sync"),
    estimateTariff: (id, tonnes) => post(`/tariffs/${encodeURIComponent(id)}/estimate`, { tonnes }),
    getMasterPolicy: () => req("/master-access/admin", { signal: AbortSignal.timeout(5000) }),
    saveMasterPolicy: (password) => put("/master-access/admin", { password }),
    getChamado: (identifier) => req(`/chamados/${encodeURIComponent(identifier)}`),
    getMasterAccess: () => req("/master-access", { signal: AbortSignal.timeout(5000) }),
    setupMasterAccess: (password) => post("/master-access/setup", { password }),
    unlockMasterAccess: (password) => post("/master-access/unlock", { password }),
    lockMasterAccess: () => req("/master-access", { method: "DELETE" }),
    getMessages: () => req("/messages"),
    saveMessages: (body) => put("/messages", body),
    listChamadosPage: (query) => req(`/chamados/page?${new URLSearchParams(Object.entries(query).map(([key, value]) => [key, String(value)]))}`),
    getChamadosSummary: () => req("/chamados/summary"),
    getDeveloperMonitor: () => req("/developer/monitor"),
    getNotifications: () => req("/notifications"),
    markNotificationRead: (id) => post(`/notifications/${encodeURIComponent(id)}/read`),
    getDeveloperNotifications: () => req("/developer/notifications"),
    publishNotification: (body) => post("/developer/notifications", body),
    archiveNotification: (id) => post(`/developer/notifications/${encodeURIComponent(id)}/archive`),
    getSchedules: () => req("/schedules"),
    getScheduleHistory: (id, page) => req(`/schedules/${encodeURIComponent(id)}/history?page=${page}`),
    createSchedule: (body) => post("/schedules", body),
    updateSchedule: (id, body) => put(`/schedules/${encodeURIComponent(id)}`, body),
    removeSchedule: (id) => req(`/schedules/${encodeURIComponent(id)}`, { method: "DELETE" }),
    runSchedule: (id) => post(`/schedules/${encodeURIComponent(id)}/run`),
    getDeveloperConfig: () => req("/developer"),
    testReleaseConnection: () => post("/developer/releases/test"),
    getPublishStatus: () => req("/developer/releases/publish"),
    publishRelease: (body) => post("/developer/releases/publish", body),
    getUpdateStatus: () => req("/updates"),
    checkUpdates: () => post("/updates/check"),
    downloadUpdate: () => post("/updates/download"),
    installUpdate: () => post("/updates/install"),
    getSession: () => req("/session", { signal: AbortSignal.timeout(5000) }),
    async login(operatorName) {
      const value = await post<import("./types").SessionState>("/session", { operator_name: operatorName });
      if (value.session) sessionStorage.setItem(sessionKey, value.session.id);
      return value;
    },
    async logout() { await req("/session", { method: "DELETE" }); sessionStorage.removeItem(sessionKey); },
    async ping() {
      const t = performance.now();
      const r = await req<{ versao: string }>("/health/ping");
      return { ok: true, versao: r.versao, latenciaMs: Math.round(performance.now() - t) };
    },
    getOverview: () => req("/overview"),
    listCtes: () => req("/ctes"),
    refreshCtes: (periodoDias, range) => post("/ctes/refresh", { periodoDias, ...range }),
    getRun: () => req("/runs/current"),
    startRun: (body) => post("/runs", body),
    stopRun: () => post("/runs/current/stop"),
    listDacteJobs: async () => (await req<DacteJob[]>("/documents/dacte/jobs")).map((job) => ({
      ...job, ...(job.id && job.state === "concluida"
        ? { pdfUrl: `${baseUrl.replace(/\/$/, "")}/documents/dacte/file/${encodeURIComponent(job.id)}` } : {}),
    })),
    generateDacte: (ctes, metodo) => post("/documents/dacte/generate", { ctes, metodo }),
    listChamados: () => req("/chamados"),
    listLogs: (since) => req(`/logs${since ? `?since=${encodeURIComponent(since)}` : ""}`),
    getBrowserFrame: () => req("/automation/browser"),
    focusBrowser: () => post("/automation/browser/focus"),
    getHealth: () => req("/health/diagnostics"),
    getConfig: () => req("/config"),
    saveConfig: (g) => put("/config", g),
    listSteps: () => req("/automation/steps"),
    saveSteps: (s) => put("/automation/steps", s),
  };
}
