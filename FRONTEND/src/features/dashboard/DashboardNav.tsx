import {
  ChevronDown,
  ChevronRight,
  ClipboardList,
  Crosshair,
  ListChecks,
  Maximize2,
  PanelLeftClose,
  PanelLeftOpen,
  PencilLine,
  Play,
  SlidersHorizontal,
} from "lucide-react";
import { useState } from "react";

export type DashboardView =
  | "execution"
  | "chamados"
  | "pendentes-plan"
  | "mapping"
  | "steps"
  | "editor"
  | "rodopar-control"
  | "live-browser"
  | "env";

interface Props {
  activeView: DashboardView;
  collapsed: boolean;
  envCount: number;
  mapCount: number;
  stepCount: number;
  onChange: (view: DashboardView) => void;
  onCollapsedChange: (collapsed: boolean) => void;
}

type NavNode = {
  id: string;
  label: string;
  icon?: typeof Play;
  view?: DashboardView;
  children?: NavNode[];
};

const NAV_TREE: NavNode[] = [
  { id: "execution", label: "Execução", icon: Play, view: "execution" },
  { id: "live-browser", label: "Navegador ao vivo", icon: Maximize2, view: "live-browser" },
  { id: "pendentes-plan", label: "CTEs pendentes", icon: ListChecks, view: "pendentes-plan" },
  { id: "chamados", label: "Chamados", icon: ClipboardList, view: "chamados" },
  {
    id: "mapping-root",
    label: "Mapeamento",
    icon: Crosshair,
    children: [
      { id: "mapping", label: "Pontos e abas", icon: Crosshair, view: "mapping" },
      { id: "steps", label: "Passos", icon: ListChecks, view: "steps" },
      { id: "editor", label: "Editor", icon: PencilLine, view: "editor" },
      { id: "rodopar-control", label: "Controle Rodopar", icon: Crosshair, view: "rodopar-control" },
    ],
  },
  {
    id: "settings-root",
    label: "Configuração",
    icon: SlidersHorizontal,
    children: [{ id: "env", label: "Env", icon: SlidersHorizontal, view: "env" }],
  },
];

const COLLAPSED_NAV_TREE = NAV_TREE.flatMap((node) =>
  node.view ? [node] : node.children?.filter((child) => child.view) ?? [],
);

export function DashboardNav({
  activeView,
  collapsed,
  envCount,
  mapCount,
  stepCount,
  onChange,
  onCollapsedChange,
}: Props) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({
    "mapping-root": true,
    "settings-root": true,
  });

  function badgeFor(key: DashboardView) {
    if (key === "mapping") return mapCount;
    if (key === "steps") return stepCount;
    if (key === "env") return envCount;
    return null;
  }

  function nodeIsActive(node: NavNode): boolean {
    return node.view === activeView || Boolean(node.children?.some(nodeIsActive));
  }

  function firstChildView(node: NavNode) {
    return node.children?.find((child) => child.view)?.view;
  }

  function renderNode(node: NavNode, depth = 0) {
    const Icon = node.icon;
    const active = nodeIsActive(node);
    const hasChildren = Boolean(node.children?.length);
    const open = expanded[node.id] ?? active;
    const badge = node.view ? badgeFor(node.view) : null;

    return (
      <div className="sidebar-node" key={node.id}>
        <button
          className={active ? "sidebar-link active" : "sidebar-link"}
          data-depth={depth}
          onClick={() => {
            if (collapsed && hasChildren) {
              const target = firstChildView(node);
              if (target) onChange(target);
              return;
            }
            if (hasChildren) setExpanded((current) => ({ ...current, [node.id]: !open }));
            if (node.view) onChange(node.view);
          }}
          title={node.label}
          type="button"
        >
          {collapsed && Icon ? (
            <Icon size={16} aria-hidden="true" />
          ) : hasChildren ? (
            open ? <ChevronDown size={15} aria-hidden="true" /> : <ChevronRight size={15} aria-hidden="true" />
          ) : Icon ? (
            <Icon size={16} aria-hidden="true" />
          ) : (
            <span />
          )}
          <span className="sidebar-label">{node.label}</span>
          {badge !== null ? <small>{badge}</small> : null}
        </button>
        {hasChildren && open && !collapsed ? (
          <div className="sidebar-children">
            {node.children!.map((child) => renderNode(child, depth + 1))}
          </div>
        ) : null}
      </div>
    );
  }

  const visibleNodes = collapsed ? COLLAPSED_NAV_TREE : NAV_TREE;

  return (
    <aside
      className={collapsed ? "dashboard-sidebar is-collapsed" : "dashboard-sidebar"}
      onMouseLeave={() => {
        if (!collapsed) onCollapsedChange(true);
      }}
    >
      <div className="sidebar-top">
        <button
          className="sidebar-toggle"
          onClick={() => onCollapsedChange(!collapsed)}
          title={collapsed ? "Expandir menu" : "Recolher menu"}
          type="button"
        >
          {collapsed ? <PanelLeftOpen size={17} aria-hidden="true" /> : <PanelLeftClose size={17} aria-hidden="true" />}
        </button>
      </div>
      <div className="sidebar-section">
        {visibleNodes.map((node) => renderNode(node))}
      </div>
    </aside>
  );
}
