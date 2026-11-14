import { useRouterState } from "@tanstack/react-router";
import { Database, FlaskConical } from "lucide-react";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { Separator } from "@/components/ui/separator";
import { useApi } from "@/services";
import { navItems, adminItems, developerItems } from "./app-sidebar";
import { cn } from "@/lib/utils";
import { OperatorMenu, useOperator } from "./session-gate";
import { NotificationBell } from "./notification-provider";

export function AppHeader() {
  const { mode, setMode } = useApi();
  const { session } = useOperator();
  const path = useRouterState({ select: (r) => r.location.pathname });
  const current = [...navItems, ...adminItems, ...developerItems].find((i) => i.url === path);
  return (
    <header className="sticky top-0 z-20 flex min-h-12 shrink-0 items-center gap-2 border-b bg-card px-2 py-2 lg:px-4">
      <SidebarTrigger />
      <Separator orientation="vertical" className="h-5" />
      <h1 className="min-w-0 flex-1 truncate text-sm font-semibold">
        {current?.title ?? "Automação Novelis"}
      </h1>
      <div className="ml-auto flex shrink-0 items-center justify-end gap-2 text-xs">
        {!session && (
          <div
            className="inline-flex overflow-hidden rounded border"
            role="group"
            aria-label="Fonte de dados"
          >
            <button
              onClick={() => setMode("demo")}
              className={cn(
                "inline-flex items-center gap-1 px-2 py-1",
                mode === "demo"
                  ? "bg-warning text-warning-foreground font-semibold"
                  : "hover:bg-muted",
              )}
            >
              <FlaskConical className="h-3.5 w-3.5" />
              Demonstração
            </button>
            <button
              onClick={() => setMode("local")}
              className={cn(
                "inline-flex items-center gap-1 border-l px-2 py-1",
                mode === "local"
                  ? "bg-primary text-primary-foreground font-semibold"
                  : "hover:bg-muted",
              )}
            >
              <Database className="h-3.5 w-3.5" />
              Backend local
            </button>
          </div>
        )}
        <NotificationBell />
        <OperatorMenu />
      </div>
    </header>
  );
}
