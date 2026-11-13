import type { AutomationApi, DacteJob } from "./types";

export function createHttpApi(baseUrl: string): AutomationApi {
  const sessionKey = `novelis.operator-session:${baseUrl.replace(/\/$/, "")}`;
  const token = () => typeof window === "undefined" ? null : sessionStorage.getItem(sessionKey);
  const req = async <T,>(path: string, init?: RequestInit): Promise<T> => {
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
  };
  const post = <T,>(p: string, body?: unknown) => req<T>(p, { method: "POST", body: JSON.stringify(body ?? {}) });
  const put = <T,>(p: string, body: unknown) => req<T>(p, { method: "PUT", body: JSON.stringify(body) });
  return {
    getSession: () => req("/session"),
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
    refreshCtes: (periodoDias) => post("/ctes/refresh", { periodoDias }),
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
