import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { createHttpApi } from "./http";
import { mockApi } from "./mock";
import type { AutomationApi } from "./types";

export type ApiMode = "demo" | "local";
export const DEFAULT_BASE_URL = import.meta.env["VITE_API_BASE_URL"] || "http://127.0.0.1:8000/api/hub";

interface Ctx { api: AutomationApi; mode: ApiMode; setMode: (m: ApiMode) => void; baseUrl: string; setBaseUrl: (u: string) => void }
const ApiContext = createContext<Ctx | null>(null);

export function ApiProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [mode, setModeState] = useState<ApiMode>(import.meta.env["VITE_DEFAULT_API_MODE"] === "local" ? "local" : "demo");
  const [baseUrl, setBaseUrlState] = useState(DEFAULT_BASE_URL);
  useEffect(() => {
    const m = localStorage.getItem("an.mode");
    if (m === "demo" || m === "local") setModeState(m);
    const u = localStorage.getItem("an.baseUrl");
    if (u?.replace(/\/$/, "") === "http://192.168.254.250:8000/api/hub") {
      localStorage.setItem("an.baseUrl", DEFAULT_BASE_URL);
      setBaseUrlState(DEFAULT_BASE_URL);
    } else if (u) setBaseUrlState(u);
  }, []);
  const value = useMemo<Ctx>(() => ({
    api: mode === "demo" ? mockApi : createHttpApi(baseUrl),
    mode, baseUrl,
    setMode: (m) => { localStorage.setItem("an.mode", m); setModeState(m); qc.clear(); },
    setBaseUrl: (u) => { localStorage.setItem("an.baseUrl", u); setBaseUrlState(u); qc.clear(); },
  }), [mode, baseUrl, qc]);
  return <ApiContext.Provider value={value}>{children}</ApiContext.Provider>;
}

export function useApi() {
  const c = useContext(ApiContext);
  if (!c) throw new Error("useApi fora do ApiProvider");
  return c;
}

export * from "./types";
