import { Activity, Settings2 } from "lucide-react";
import type { PropsWithChildren } from "react";

export function AppShell({ children }: PropsWithChildren) {
  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <Activity size={22} aria-hidden="true" />
          <div>
            <strong>Automação Novelis</strong>
            <span>Auditoria CTE Ocorrência</span>
          </div>
        </div>
        <div className="topbar-status">
          <Settings2 size={16} aria-hidden="true" />
          <span>Automação Novelis</span>
        </div>
      </header>
      <main>{children}</main>
    </div>
  );
}
