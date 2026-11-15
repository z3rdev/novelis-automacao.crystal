import { Link, useRouterState } from "@tanstack/react-router";
import { Database, FlaskConical } from "lucide-react";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { Separator } from "@/components/ui/separator";
import { useApi } from "@/services";
import { allNavigationItems } from "./navigation";
import { cn } from "@/lib/utils";
import { OperatorMenu, useOperator } from "./session-gate";
import { contextualHelp } from "./help-content";
import { FluentIcon } from "./fluent-icon";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { AppearanceMenu } from "./appearance-menu";

export function AppHeader() {
  const { mode, setMode } = useApi();
  const { session } = useOperator();
  const path = useRouterState({ select: (r) => r.location.pathname });
  const current = allNavigationItems.find((i) => i.url === path);
  return (
    <header className="sticky top-0 z-20 flex h-12 shrink-0 items-center gap-2 border-b bg-card px-2 lg:px-4">
      <SidebarTrigger />
      <Separator orientation="vertical" className="h-5" />
      <h1 className="min-w-0 flex-1 truncate text-sm font-semibold">
        {current?.headerTitle ?? current?.title ?? "Automação Novelis"}
      </h1>
      <div className="ml-auto flex shrink-0 items-center justify-end gap-2 text-xs">
        <AppearanceMenu />
        {contextualHelp[path] && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon" asChild>
                <Link
                  to="/ajuda"
                  search={{ topic: contextualHelp[path] }}
                  aria-label="Ajuda desta tela"
                >
                  <FluentIcon name="help" />
                </Link>
              </Button>
            </TooltipTrigger>
            <TooltipContent>Ajuda desta tela</TooltipContent>
          </Tooltip>
        )}
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
        <OperatorMenu />
      </div>
    </header>
  );
}
