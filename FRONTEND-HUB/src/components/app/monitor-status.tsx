import { cn } from "@/lib/utils";

const states: Record<string, string> = {
  stopped: "Parada",
  running: "Executando",
  stopping: "Parando",
  broken: "Falha",
  cancelled: "Cancelada",
  completed: "Concluída",
  active: "Conectado",
  logged_out: "Saiu da sessão",
  interrupted: "Interrompida",
  stale: "Sem sinal",
};

export const installationLabels = {
  installed: "Instalado",
  development: "Desenvolvimento",
  unreported: "Não informado",
};

export function MonitorStatus({ value, muted = false }: { value: string; muted?: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2 py-1 text-xs font-medium",
        muted
          ? "border-border bg-muted text-muted-foreground"
          : ["running", "active"].includes(value)
            ? "border-teal-500/25 bg-teal-500/10 text-info"
            : value === "broken"
              ? "border-destructive/20 bg-destructive/10 text-destructive"
              : ["stopping", "stale", "interrupted"].includes(value)
                ? "border-amber-500/25 bg-amber-500/10 text-warning-foreground"
                : "border-border bg-muted text-muted-foreground",
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {states[value] ?? "Não informado"}
    </span>
  );
}

export function DeviceConnection({ online }: { online: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap text-xs font-medium",
        online ? "text-info" : "text-muted-foreground",
      )}
    >
      <span className={cn("h-2 w-2 rounded-full", online ? "bg-teal-500" : "bg-slate-400")} />
      {online ? "Online" : "Offline"}
    </span>
  );
}
