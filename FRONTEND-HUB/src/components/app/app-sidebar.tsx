import { Link, useRouterState } from "@tanstack/react-router";
import { LayoutDashboard, PlayCircle, ListChecks, FileText, Ticket, MonitorPlay, Settings, Wrench, Truck } from "lucide-react";
import { Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarGroupContent, SidebarGroupLabel, SidebarHeader, SidebarMenu, SidebarMenuButton, SidebarMenuItem, useSidebar } from "@/components/ui/sidebar";

export const navItems = [
  { title: "Visão geral", url: "/", icon: LayoutDashboard },
  { title: "Execução e lotes", url: "/execucao", icon: PlayCircle },
  { title: "CT-es pendentes", url: "/pendentes", icon: ListChecks },
  { title: "Documentos e DACTE", url: "/documentos", icon: FileText },
  { title: "Chamados Novelis", url: "/chamados", icon: Ticket },
  { title: "Monitor da automação", url: "/monitor", icon: MonitorPlay },
] as const;
export const adminItems = [
  { title: "Configurações e diagnóstico", url: "/configuracoes", icon: Settings },
  { title: "Área avançada", url: "/avancado", icon: Wrench },
] as const;

export function AppSidebar() {
  const { state } = useSidebar();
  const collapsed = state === "collapsed";
  const path = useRouterState({ select: (r) => r.location.pathname });
  const render = (items: readonly { title: string; url: string; icon: React.ComponentType<{ className?: string }> }[]) =>
    items.map((i) => (
      <SidebarMenuItem key={i.url}>
        <SidebarMenuButton asChild isActive={path === i.url} tooltip={i.title}>
          <Link to={i.url}><i.icon className="h-4 w-4" /><span>{i.title}</span></Link>
        </SidebarMenuButton>
      </SidebarMenuItem>
    ));
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <div className="flex items-center gap-2 px-1 py-1.5">
          <div className="grid h-8 w-8 shrink-0 place-items-center rounded bg-sidebar-primary text-sidebar-primary-foreground"><Truck className="h-4 w-4" /></div>
          {!collapsed && <div className="leading-tight"><div className="text-sm font-semibold text-sidebar-accent-foreground">Automação Novelis</div><div className="text-[11px] opacity-70">Operação de CT-es</div></div>}
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup><SidebarGroupLabel>Operação</SidebarGroupLabel><SidebarGroupContent><SidebarMenu>{render(navItems)}</SidebarMenu></SidebarGroupContent></SidebarGroup>
        <SidebarGroup><SidebarGroupLabel>Administração</SidebarGroupLabel><SidebarGroupContent><SidebarMenu>{render(adminItems)}</SidebarMenu></SidebarGroupContent></SidebarGroup>
      </SidebarContent>
      <SidebarFooter>{!collapsed && <div className="px-2 pb-1 text-[11px] opacity-60">v0.1.0 · Cargo Hub</div>}</SidebarFooter>
    </Sidebar>
  );
}
