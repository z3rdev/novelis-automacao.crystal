import { Link, useRouterState } from "@tanstack/react-router";
import {
  LayoutDashboard,
  PlayCircle,
  ListChecks,
  FileText,
  Ticket,
  MonitorPlay,
  Settings,
  Wrench,
  CalendarClock,
  BellRing,
  UsersRound,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useApi } from "@/services";
import { BrandMark, BrandName } from "./brand";
import { SidebarStatus } from "./sidebar-status";
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

export const navItems = [
  { title: "Visão geral", url: "/", icon: LayoutDashboard },
  { title: "Execução e lotes", url: "/execucao", icon: PlayCircle },
  { title: "CT-es pendentes", url: "/pendentes", icon: ListChecks },
  { title: "Documentos e DACTE", url: "/documentos", icon: FileText },
  { title: "Chamados Novelis", url: "/chamados", icon: Ticket },
  { title: "Monitor da automação", url: "/monitor", icon: MonitorPlay },
  { title: "Agendamentos", url: "/agendamentos", icon: CalendarClock },
] as const;

export const developerItems = [
  { title: "Usuários e dispositivos", url: "/usuarios-dev", icon: UsersRound },
  { title: "Central de notificações", url: "/notificacoes-dev", icon: BellRing },
] as const;
export const adminItems = [
  { title: "Configurações e diagnóstico", url: "/configuracoes", icon: Settings },
  { title: "Área avançada", url: "/avancado", icon: Wrench },
] as const;

export function AppSidebar() {
  const { state } = useSidebar();
  const { api, mode, baseUrl } = useApi();
  const developer = useQuery({
    queryKey: ["developer-config", mode, baseUrl],
    queryFn: () => api.getDeveloperConfig(),
    enabled: mode === "local",
    refetchInterval: 15000,
    retry: 0,
  });
  const collapsed = state === "collapsed";
  const path = useRouterState({ select: (r) => r.location.pathname });
  const render = (
    items: readonly {
      title: string;
      url: string;
      icon: React.ComponentType<{ className?: string }>;
    }[],
  ) =>
    items.map((i) => (
      <SidebarMenuItem key={i.url}>
        <SidebarMenuButton asChild isActive={path === i.url} tooltip={i.title}>
          <Link to={i.url}>
            <i.icon className="h-4 w-4" />
            <span>{i.title}</span>
          </Link>
        </SidebarMenuButton>
      </SidebarMenuItem>
    ));
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <div className="flex items-center gap-3 px-1 py-3">
          <BrandMark tone="white" className={collapsed ? "h-8 w-8" : "h-11 w-11"} />
          {!collapsed && (
            <div className="leading-tight">
              <BrandName className="text-xl text-white" />
              <div className="mt-1 text-[11px] opacity-65">Automação Novelis</div>
            </div>
          )}
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Operação</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>{render(navItems)}</SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
        <SidebarGroup>
          <SidebarGroupLabel>Administração</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>{render(adminItems)}</SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
        {mode === "local" && developer.data?.enabled && (
          <SidebarGroup>
            <SidebarGroupLabel>Desenvolvimento</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>{render(developerItems)}</SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        )}
      </SidebarContent>
      <SidebarFooter>
        <SidebarStatus />
      </SidebarFooter>
    </Sidebar>
  );
}
