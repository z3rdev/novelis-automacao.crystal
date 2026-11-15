import { useEffect, useRef, useState } from "react";
import { Link, useRouterState } from "@tanstack/react-router";
import { Search, X } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useApi } from "@/services";
import { Input } from "@/components/ui/input";
import { BrandMark, BrandName } from "./brand";
import { SidebarStatus } from "./sidebar-status";
import { SidebarSettings } from "./sidebar-settings";
import { useNotifications } from "./notification-provider";
import { useRun } from "./run-panel";
import { runLabel } from "./status";
import {
  footerItems,
  matchesNavigation,
  navigationGroups,
  overviewItem,
  settingsItems,
  type NavigationItem,
} from "./navigation";
import "./app-sidebar.css";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";

export function AppSidebar() {
  const { state, isMobile, setOpen, setOpenMobile } = useSidebar();
  const { api, mode, baseUrl } = useApi();
  const notifications = useNotifications();
  const chat = useQuery({ queryKey: ["chat-inbox", mode, baseUrl], queryFn: () => api.getChatInbox(), enabled: false });
  const run = useRun();
  const [search, setSearch] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const developer = useQuery({
    queryKey: ["developer-config", mode, baseUrl],
    queryFn: () => api.getDeveloperConfig(),
    enabled: mode === "local",
    refetchInterval: 15000,
    retry: 0,
  });
  const overview = useQuery({
    queryKey: ["overview", mode, baseUrl],
    queryFn: () => api.getOverview(),
    refetchInterval: 5000,
    retry: 0,
  });
  const chamados = useQuery({
    queryKey: ["chamados-summary", mode, baseUrl],
    queryFn: () => api.getChamadosSummary(),
    refetchInterval: 30000,
    retry: 0,
  });
  const collapsed = state === "collapsed" && !isMobile;
  const path = useRouterState({ select: (r) => r.location.pathname });
  const helpOpen = path === "/ajuda";
  useEffect(() => {
    if (helpOpen) setSearch("");
  }, [helpOpen]);
  const developerEnabled = mode === "local" && developer.data?.enabled === true;
  const navigate = () => {
    if (isMobile) setOpenMobile(false);
  };
  const groups = navigationGroups
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => matchesNavigation(item, search, group.title)),
    }))
    .filter((group) => group.items.length);
  const footer = footerItems.filter((item) => matchesNavigation(item, search));
  const showOverview = matchesNavigation(overviewItem, search);
  const hasMatches =
    showOverview ||
    groups.length > 0 ||
    footer.length > 0 ||
    settingsItems.some(
      (item) =>
        (!item.developerOnly || developerEnabled) &&
        matchesNavigation(item, search, "Configurações"),
    );
  const render = (items: NavigationItem[]) =>
    items.map((item) => {
      const count =
        item.url === "/pendentes"
          ? overview.data?.naFila
          : item.url === "/chamados"
            ? chamados.data?.counts.em_analise
            : item.url === "/notificacoes"
              ? notifications.unread
              : item.url === "/conversas"
                ? chat.data?.unread
              : undefined;
      const countLabel =
        item.url === "/pendentes"
          ? "CT-es sem chamado"
          : item.url === "/chamados"
            ? "Chamados em análise"
            : item.url === "/conversas" ? "Mensagens não lidas" : "Notificações não lidas";
      const tooltip =
        count === undefined
          ? item.title
          : `${item.title} · ${count} ${countLabel.toLocaleLowerCase("pt-BR")}`;
      return (
        <SidebarMenuItem key={item.url}>
          <SidebarMenuButton asChild isActive={path === item.url} tooltip={tooltip}>
            <Link
              to={item.url}
              onClick={navigate}
              aria-current={path === item.url ? "page" : undefined}
              aria-label={tooltip}
            >
              <item.icon />
              <span className="flex-1">{item.title}</span>
              {item.url === "/monitor" && (
                <span
                  role="img"
                  aria-label={`Automação ${run.isError ? "sem conexão" : runLabel[run.data?.state ?? "aguardando"]}`}
                  className={`cargo-run-dot cargo-run-${run.isError ? "falhou" : (run.data?.state ?? "aguardando")}`}
                />
              )}
              {count !== undefined && count > 0 && (
                <span
                  className="cargo-nav-count"
                  title={`${count} ${countLabel.toLocaleLowerCase("pt-BR")}`}
                >
                  {count > 999 ? "999+" : count}
                </span>
              )}
            </Link>
          </SidebarMenuButton>
        </SidebarMenuItem>
      );
    });
  return (
    <Sidebar collapsible="icon" className="z-30">
      <div className="cargo-sidebar flex h-full min-h-0 flex-col" data-compact={collapsed}>
        <SidebarHeader className="shrink-0 gap-0 p-0">
          <div className="flex h-12 shrink-0 items-center gap-3 border-b border-white/10 px-2">
            <BrandMark tone="white" className="h-8 w-8 shrink-0" />
            {!collapsed && (
              <div className="leading-tight">
                <BrandName className="text-xl text-white" />
              </div>
            )}
          </div>
          {!helpOpen && (
            <div className="px-2 pt-3 pb-1">
              {collapsed ? (
                <SidebarMenuButton
                  aria-label="Buscar no menu"
                  tooltip="Buscar no menu"
                  onClick={() => {
                    setOpen(true);
                    window.requestAnimationFrame(() => input.current?.focus());
                  }}
                >
                  <Search />
                </SidebarMenuButton>
              ) : (
                <div className="relative">
                  <Search className="pointer-events-none absolute left-2.5 top-2.5 h-3.5 w-3.5 text-white/50" />
                  <Input
                    ref={input}
                    aria-label="Buscar no menu"
                    placeholder="Buscar…"
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Escape") setSearch("");
                    }}
                    className="h-9 border-white/10 bg-white/5 pr-8 pl-8 text-xs text-white shadow-none placeholder:text-white/45"
                  />
                  {search && (
                    <button
                      aria-label="Limpar busca do menu"
                      onClick={() => {
                        setSearch("");
                        input.current?.focus();
                      }}
                      className="absolute right-2 top-2.5 text-white/65"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              )}
            </div>
          )}
        </SidebarHeader>
        <SidebarContent
          role="navigation"
          aria-label="Navegação principal"
          className="gap-0 group-data-[collapsible=icon]:overflow-auto"
        >
          {showOverview && (
            <SidebarGroup className="pt-2 pb-0">
              <SidebarMenu>{render([overviewItem])}</SidebarMenu>
            </SidebarGroup>
          )}
          {groups.map((group) => (
            <SidebarGroup key={group.title} role="group" aria-label={group.title}>
              <SidebarGroupLabel>{group.title}</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>{render(group.items)}</SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          ))}
          {!hasMatches && (
            <p role="status" className="px-4 py-6 text-xs text-white/60">
              Nenhuma página encontrada.
            </p>
          )}
        </SidebarContent>
        <SidebarFooter className="shrink-0 gap-1 border-t border-white/10 p-2">
          <nav
            aria-label="Ajuda e configurações"
            className="max-h-[45svh] overflow-y-auto group-data-[collapsible=icon]:overflow-visible"
          >
            <SidebarMenu>
              {render(footer)}
              <SidebarSettings
                path={path}
                collapsed={collapsed}
                developer={developerEnabled}
                search={search}
                onNavigate={navigate}
              />
            </SidebarMenu>
          </nav>
          <SidebarStatus updatedAt={overview.data?.ultimaAtualizacao} />
        </SidebarFooter>
      </div>
    </Sidebar>
  );
}
