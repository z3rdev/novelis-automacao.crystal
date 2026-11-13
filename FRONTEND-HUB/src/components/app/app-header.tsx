import { useQuery } from "@tanstack/react-query";
import { useRouterState } from "@tanstack/react-router";
import { Database, FlaskConical, RefreshCw, Wifi, WifiOff } from "lucide-react";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { Separator } from "@/components/ui/separator";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useApi } from "@/services";
import { fmtDateTime, fmtTime } from "@/lib/format";
import { navItems, adminItems } from "./app-sidebar";
import { cn } from "@/lib/utils";

export function AppHeader() {
  const { api, mode, setMode, baseUrl } = useApi();
  const path = useRouterState({ select: (r) => r.location.pathname });
  const current = [...navItems, ...adminItems].find((i) => i.url === path);
  const ping = useQuery({ queryKey: ["ping", mode, baseUrl], queryFn: () => api.ping(), refetchInterval: 10000, retry: 0 });
  const ov = useQuery({ queryKey: ["overview", mode, baseUrl], queryFn: () => api.getOverview(), refetchInterval: 5000, retry: 0 });
  const online = ping.isSuccess;
  return (
    <header className="sticky top-0 z-20 flex min-h-12 shrink-0 flex-wrap items-center gap-2 border-b bg-card px-2 py-2 lg:px-4">
      <SidebarTrigger />
      <Separator orientation="vertical" className="h-5" />
      <h1 className="truncate text-sm font-semibold">{current?.title ?? "Automação Novelis"}</h1>
      <div className="ml-auto flex max-w-full flex-wrap items-center justify-end gap-2 text-xs">
        <span className="hidden items-center gap-1 text-muted-foreground md:inline-flex"><RefreshCw className={cn("h-3.5 w-3.5", ov.isFetching && "animate-spin")} />Dados: {fmtDateTime(ov.data?.ultimaAtualizacao)}</span>
        <Tooltip>
          <TooltipTrigger asChild>
            <span className={cn("inline-flex items-center gap-1 rounded border px-2 py-1 font-medium", online ? "border-success/30 bg-success/10 text-success" : ping.isLoading ? "border-info/30 bg-info/10 text-info" : "border-destructive/30 bg-destructive/10 text-destructive")}>
              {online ? <Wifi className="h-3.5 w-3.5" /> : <WifiOff className="h-3.5 w-3.5" />}
              {online ? `Conectado · ${ping.data.latenciaMs} ms` : ping.isLoading ? "Conectando…" : "Sem conexão"}
            </span>
          </TooltipTrigger>
          <TooltipContent>{mode === "demo" ? "Adaptador de demonstração" : baseUrl} · verificado {fmtTime(new Date(ping.dataUpdatedAt || Date.now()).toISOString())}</TooltipContent>
        </Tooltip>
        <div className="inline-flex overflow-hidden rounded border" role="group" aria-label="Fonte de dados">
          <button onClick={() => setMode("demo")} className={cn("inline-flex items-center gap-1 px-2 py-1", mode === "demo" ? "bg-warning text-warning-foreground font-semibold" : "hover:bg-muted")}><FlaskConical className="h-3.5 w-3.5" />Demonstração</button>
          <button onClick={() => setMode("local")} className={cn("inline-flex items-center gap-1 border-l px-2 py-1", mode === "local" ? "bg-primary text-primary-foreground font-semibold" : "hover:bg-muted")}><Database className="h-3.5 w-3.5" />Backend local</button>
        </div>
      </div>
    </header>
  );
}
