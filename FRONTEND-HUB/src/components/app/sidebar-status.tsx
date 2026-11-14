import { useQuery } from "@tanstack/react-query";
import { Clock3, Monitor, RefreshCw, Wifi, WifiOff } from "lucide-react";
import { useApi } from "@/services";
import { fmtDateTime, fmtTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useSidebar } from "@/components/ui/sidebar";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useOperator } from "./session-gate";
import { UpdateButton } from "./update-provider";

export function SidebarStatus() {
  const { api, mode, baseUrl } = useApi();
  const { session } = useOperator();
  const { state } = useSidebar();
  const collapsed = state === "collapsed";
  const ping = useQuery({
    queryKey: ["ping", mode, baseUrl],
    queryFn: () => api.ping(),
    refetchInterval: 10000,
    retry: 0,
  });
  const overview = useQuery({
    queryKey: ["overview", mode, baseUrl],
    queryFn: () => api.getOverview(),
    refetchInterval: 5000,
    retry: 0,
  });
  const online = ping.isSuccess;
  const status = online
    ? `Conectado · ${ping.data.latenciaMs} ms`
    : ping.isLoading
      ? "Conectando…"
      : "Sem conexão";
  const dataLabel = `Dados ${fmtDateTime(overview.data?.ultimaAtualizacao)}`;
  return (
    <div
      data-testid="sidebar-status"
      className="space-y-2 border-t border-sidebar-border pt-2 text-sidebar-foreground"
    >
      <UpdateButton sidebar />
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            tabIndex={0}
            className={cn(
              "flex min-w-0 items-center gap-2 rounded-md px-2 py-1.5 text-xs",
              online
                ? "bg-emerald-400/10 text-emerald-300"
                : ping.isLoading
                  ? "text-sidebar-foreground/70"
                  : "bg-red-400/10 text-red-300",
            )}
            aria-label={status}
          >
            {online ? (
              <Wifi className="h-4 w-4 shrink-0" />
            ) : (
              <WifiOff className="h-4 w-4 shrink-0" />
            )}
            {!collapsed && <span className="truncate">{status}</span>}
          </div>
        </TooltipTrigger>
        <TooltipContent side="right">
          {status} · {mode === "demo" ? "Demonstração" : baseUrl} · verificado{" "}
          {fmtTime(new Date(ping.dataUpdatedAt || Date.now()).toISOString())}
        </TooltipContent>
      </Tooltip>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            tabIndex={0}
            aria-label={dataLabel}
            className="flex min-w-0 items-start gap-2 px-2 py-1 text-xs text-sidebar-foreground/65"
          >
            {overview.isFetching ? (
              <RefreshCw className="mt-0.5 h-4 w-4 shrink-0 animate-spin" />
            ) : (
              <Clock3 className="mt-0.5 h-4 w-4 shrink-0" />
            )}
            {!collapsed && (
              <div className="min-w-0">
                <span className="block text-[10px] uppercase tracking-wide">Dados atualizados</span>
                <span className="block truncate">
                  {fmtDateTime(overview.data?.ultimaAtualizacao)}
                </span>
              </div>
            )}
          </div>
        </TooltipTrigger>
        <TooltipContent side="right">{dataLabel}</TooltipContent>
      </Tooltip>
      {session && (
        <Tooltip>
          <TooltipTrigger asChild>
            <div className="flex min-w-0 items-center gap-2 border-t border-sidebar-border px-2 py-2 text-xs text-sidebar-foreground/65">
              <Monitor className="h-4 w-4 shrink-0" />
              {!collapsed && <span className="truncate">{session.computer_name}</span>}
            </div>
          </TooltipTrigger>
          <TooltipContent side="right">{session.computer_name}</TooltipContent>
        </Tooltip>
      )}
    </div>
  );
}
