import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function PageBody({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("mx-auto w-full max-w-[1600px] space-y-4 p-4 lg:p-6", className)}>{children}</div>;
}

export function Kpi({ label, value, icon: Icon, tone = "neutral", hint }: { label: string; value: ReactNode; icon: React.ComponentType<{ className?: string }>; tone?: "success" | "warning" | "error" | "info" | "neutral"; hint?: ReactNode }) {
  const bar = { success: "bg-success", warning: "bg-warning", error: "bg-destructive", info: "bg-info", neutral: "bg-border" }[tone];
  return (
    <div className="relative overflow-hidden rounded-md border bg-card p-4">
      <span className={cn("absolute inset-y-0 left-0 w-1", bar)} />
      <div className="flex items-center justify-between gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
        <Icon className="h-4 w-4" />
      </div>
      <div className="mt-2 text-2xl font-semibold tabular-nums">{typeof value === "number" ? value.toLocaleString("pt-BR") : value}</div>
      {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
    </div>
  );
}

export function Section({ title, actions, children, className }: { title: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cn("min-w-0 rounded-md border bg-card", className)}>
      <header className="flex flex-wrap items-center justify-between gap-2 border-b px-4 py-2.5">
        <h2 className="min-w-0 break-words text-sm font-semibold [overflow-wrap:anywhere]">{title}</h2>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </header>
      <div className="p-4">{children}</div>
    </section>
  );
}

/** Contêiner de tabela com rolagem e cabeçalho fixo */
export function TableBox({ children, maxH = "max-h-[60vh]" }: { children: ReactNode; maxH?: string }) {
  return <div className={cn("overflow-auto rounded-md border [&_thead_th]:sticky [&_thead_th]:top-0 [&_thead_th]:z-10 [&_thead_th]:bg-muted", maxH)}>{children}</div>;
}
