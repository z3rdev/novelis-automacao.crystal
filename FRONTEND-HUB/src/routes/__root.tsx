import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  Link,
  createRootRouteWithContext,
  useRouter,
  HeadContent,
  Scripts,
  type ErrorComponentProps,
  useRouterState,
} from "@tanstack/react-router";
import { useEffect, type ReactNode } from "react";

import { SidebarProvider } from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";
import { AppSidebar } from "@/components/app/app-sidebar";
import { AppHeader } from "@/components/app/app-header";
import { ApiProvider } from "@/services";
import { SessionGate } from "@/components/app/session-gate";
import { StartupScreen } from "@/components/app/startup-screen";
import { UpdateProvider } from "@/components/app/update-provider";
import { AppDialogs } from "@/components/app/app-dialogs";
import { NotificationProvider } from "@/components/app/notification-provider";
import { WorkflowCompletionMonitor } from "@/components/app/workflow/workflow-completion";
import { AppearanceProvider } from "@/components/app/appearance-provider";
import { StatusWidgetBridge } from "@/components/app/widget/status-widget-bridge";
import { ChatMonitor } from "@/components/app/chat/chat-monitor";
import { appearanceBootScript } from "@/services/appearance";
import appCss from "../styles.css?url";
import { reportLovableError } from "../lib/lovable-error-reporting";

function NotFoundComponent() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-7xl font-bold text-foreground">404</h1>
        <h2 className="mt-4 text-xl font-semibold text-foreground">Página não encontrada</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          A página procurada não existe.
        </p>
        <div className="mt-6">
          <Link
            to="/"
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Ir para a visão geral
          </Link>
        </div>
      </div>
    </div>
  );
}

function ErrorComponent({ error, reset }: ErrorComponentProps) {
  console.error(error);
  const router = useRouter();
  useEffect(() => {
    reportLovableError(error, { boundary: "tanstack_root_error_component" });
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-xl font-semibold tracking-tight text-foreground">
          Não foi possível carregar esta tela
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Ocorreu um erro. Tente novamente ou volte à visão geral.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <button
            onClick={() => {
              router.invalidate();
              reset();
            }}
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Tentar novamente
          </button>
          <a
            href="/"
            className="inline-flex items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent"
          >
            Ir para a visão geral
          </a>
        </div>
      </div>
    </div>
  );
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  head: () => ({
    // Replace these placeholders with the app's name and description when first building the app.
    // Each content route, / included, must still set its own head(). Never add og:image or
    // twitter:image here: every page without its own would inherit the root's preview image.
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "Automação Novelis" },
      { name: "description", content: "Controle de CT-es, documentos e chamados no portal Novelis." },
      { property: "og:title", content: "Automação Novelis" },
      { property: "og:description", content: "Controle de CT-es, documentos e chamados no portal Novelis." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
          ],
    links: [
      {
        rel: "stylesheet",
        href: appCss,
      },
      { rel: "icon", href: "/favicon.ico", type: "image/x-icon" },
      { rel: "icon", href: "/favicon-32x32.png", type: "image/png", sizes: "32x32" },
      { rel: "icon", href: "/favicon-16x16.png", type: "image/png", sizes: "16x16" },
      { rel: "apple-touch-icon", href: "/apple-touch-icon.png", sizes: "180x180" },
    ],
  }),
  shellComponent: RootShell,
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});

function RootShell({ children }: { children: ReactNode }) {
  if (import.meta.env.MODE === "desktop") return <>{children}</>;
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: appearanceBootScript }} />
        <HeadContent />
      </head>
      <body>
        {children}
        <Scripts />
      </body>
    </html>
  );
}

function RootComponent() {
  const inboxOpen = useRouterState({ select: (state) => state.location.pathname === "/notificacoes" });
  const { queryClient } = Route.useRouteContext();

  return (
    <AppearanceProvider><QueryClientProvider client={queryClient}>
      {/* Required: nested routes render here. Removing <Outlet /> breaks all child routes. */}
      <ApiProvider>
        <StatusWidgetBridge />
        <StartupScreen>
        <TooltipProvider delayDuration={200}>
          <SessionGate><AppDialogs><NotificationProvider inboxOpen={inboxOpen}><UpdateProvider><SidebarProvider>
            <WorkflowCompletionMonitor />
            <ChatMonitor />
            <div className="flex min-h-screen w-full">
              <AppSidebar />
              <div className="relative isolate flex min-w-0 flex-1 flex-col overflow-x-clip">
                <AppHeader />
                <main className="min-w-0 flex-1">
                  <Outlet />
                </main>
              </div>
            </div>
          </SidebarProvider></UpdateProvider></NotificationProvider></AppDialogs></SessionGate>
          <Toaster richColors position="bottom-right" />
        </TooltipProvider>
        </StartupScreen>
      </ApiProvider>
    </QueryClientProvider></AppearanceProvider>
  );
}
