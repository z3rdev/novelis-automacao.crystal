import { useQuery } from "@tanstack/react-query";
import { desktop } from "@/services/desktop";
import { networkLabel } from "@/services/network-status";
import { useApi } from "@/services";
import { fmtDateTime, fmtTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useSidebar } from "@/components/ui/sidebar";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useOperator } from "./session-gate";
import { UpdateButton } from "./update-provider";
import { NetworkStatusIcon } from "./network-status-icon";

export function SidebarStatus({ updatedAt }: { updatedAt?: string | undefined }) {
  const { api, mode, baseUrl } = useApi();
  const { session } = useOperator();
  const { state, isMobile } = useSidebar();
  const collapsed = state === "collapsed" && !isMobile;
  const ping = useQuery({
    queryKey: ["ping", mode, baseUrl],
    queryFn: () => api.ping(),
    refetchInterval: 10000,
    retry: 0,
  });
  const online = ping.isSuccess;
  const network = useQuery({
    queryKey: ["desktop-network"],
    queryFn: () => desktop.networkStatus(),
    enabled: desktop.isDesktop,
    refetchInterval: 10_000,
    networkMode: "always",
    retry: 0,
  });
  const connection = network.isSuccess
    ? network.data
    : { kind: "unknown" as const, transport: null };
  const status = online
    ? `Conectado · ${ping.data.latenciaMs} ms`
    : ping.isLoading
      ? "Conectando…"
      : "Sem conexão";
  const label = `${status} · Dados ${fmtDateTime(updatedAt)}`;
  return (
    <div
      data-testid="sidebar-status"
      className="space-y-1 border-t border-white/10 pt-1 text-sidebar-foreground"
    >
      <UpdateButton sidebar onlyAvailable />
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            tabIndex={0}
            aria-label={label}
            className={cn(
              "flex min-w-0 items-center gap-2 rounded-md px-2 py-2 text-[11px] tabular-nums",
              online ? "text-emerald-300" : ping.isLoading ? "text-white/60" : "text-red-300",
            )}
          >
            <NetworkStatusIcon value={connection} />
            {!collapsed && (
              <span className="truncate">
                {status} · {fmtTime(updatedAt).replace(/:\d{2}$/, "")}
              </span>
            )}
          </div>
        </TooltipTrigger>
        <TooltipContent side="right" className="space-y-1">
          <p>{label}</p>
          <p>{networkLabel(connection)}</p>
          {session && (
            <p>
              {session.computer_name} · {session.windows_user}
            </p>
          )}
          <p>{mode === "demo" ? "Demonstração" : baseUrl}</p>
        </TooltipContent>
      </Tooltip>
    </div>
  );
}
