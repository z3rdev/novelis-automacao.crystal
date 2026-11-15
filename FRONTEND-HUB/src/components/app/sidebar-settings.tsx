import { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import { FluentIcon } from "./fluent-icon";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
} from "@/components/ui/sidebar";
import { matchesNavigation, settingsItems } from "./navigation";

export function SidebarSettings({
  path,
  collapsed,
  developer,
  search,
  onNavigate,
}: {
  path: string;
  collapsed: boolean;
  developer: boolean;
  search: string;
  onNavigate(): void;
}) {
  const items = settingsItems.filter(
    (item) =>
      (!item.developerOnly || developer) && matchesNavigation(item, search, "Configurações"),
  );
  const active = settingsItems.some((item) => item.url === path);
  const [open, setOpen] = useState(active);
  useEffect(() => {
    if (active) setOpen(true);
  }, [path, active]);
  if (!items.length) return null;
  if (collapsed)
    return (
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton isActive={active} tooltip="Configurações" aria-label="Configurações">
              <FluentIcon name="settings" />
              <span>Configurações</span>
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent side="right" align="end" className="min-w-60">
            <DropdownMenuLabel>Configurações</DropdownMenuLabel>
            {items.map((item) => (
              <DropdownMenuItem key={item.url} asChild>
                <Link
                  to={item.url}
                  onClick={onNavigate}
                  aria-current={path === item.url ? "page" : undefined}
                >
                  <item.icon className="h-4 w-4" />
                  {item.title}
                </Link>
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    );
  return (
    <SidebarMenuItem>
      <Collapsible open={Boolean(search.trim()) || open} onOpenChange={setOpen}>
        <CollapsibleTrigger asChild>
          <SidebarMenuButton
            isActive={active}
            className="group/settings"
            aria-label="Configurações"
          >
            <FluentIcon name="settings" />
            <span className="flex-1">Configurações</span>
            <FluentIcon
              name="chevron"
              className="ml-auto transition-transform group-data-[state=open]/settings:rotate-90"
            />
          </SidebarMenuButton>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <SidebarMenuSub>
            {items.map((item) => (
              <SidebarMenuSubItem key={item.url}>
                <SidebarMenuSubButton asChild isActive={path === item.url}>
                  <Link
                    to={item.url}
                    onClick={onNavigate}
                    aria-current={path === item.url ? "page" : undefined}
                  >
                    <item.icon />
                    <span>{item.title}</span>
                  </Link>
                </SidebarMenuSubButton>
              </SidebarMenuSubItem>
            ))}
          </SidebarMenuSub>
        </CollapsibleContent>
      </Collapsible>
    </SidebarMenuItem>
  );
}
