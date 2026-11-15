import { cn } from "@/lib/utils";
import type { WorkflowRun } from "@/services/workflow-run";
import type { StageState } from "@/services";
import { workflowPeriod } from "@/services/scheduled-workflow";
import { FluentIcon, type FluentIconName } from "../fluent-icon";
import "./workflow-run-view.css";

const states: Record<StageState, { label: string; icon: FluentIconName }> = {
  aguardando: { label: "Aguardando", icon: "clock" },
  executando: { label: "Executando", icon: "refresh" },
  parando: { label: "Interrompendo", icon: "pause" },
  concluida: { label: "Concluída", icon: "check" },
  falhou: { label: "Falhou", icon: "error" },
  cancelada: { label: "Cancelada", icon: "cancel" },
  ignorada: { label: "Não executada", icon: "forward" },
};

export function WorkflowRunView({ workflow }: { workflow: WorkflowRun }) {
  return (
    <div className="workflow-run" aria-label={`Etapas de ${workflow.name}`}>
      <div className="workflow-run-heading" aria-hidden="true">
        <span>Etapa</span>
        <span>Situação</span>
        <span>Itens</span>
      </div>
      <ol className="workflow-run-list">
        {workflow.nodes.map((node) => {
          const state = states[node.state];
          const active =
            node.id === workflow.current_node_id && ["executando", "parando"].includes(node.state);
          const detail = ["executando", "parando", "falhou", "cancelada"].includes(node.state)
            ? node.detail
            : "";
          const period = ["sql", "novelis_report"].includes(node.kind)
            ? workflowPeriod(node.options)
            : "";
          const pct =
            node.total > 0
              ? Math.max(0, Math.min(100, Math.round((node.done / node.total) * 100)))
              : 0;
          return (
            <li
              key={node.id}
              data-workflow-node={node.id}
              data-state={node.state}
              aria-current={active ? "step" : undefined}
              className={cn("workflow-run-row", active && "workflow-run-active")}
            >
              <div className="workflow-run-label">
                <FluentIcon
                  name={state.icon}
                  className={cn(
                    "workflow-run-marker",
                    active && node.state === "executando" && "motion-safe:animate-spin",
                  )}
                />
                <span className="min-w-0">
                  <span className="workflow-run-title">{node.label}</span>
                  {period && <span className="workflow-run-period">{period}</span>}
                  {detail && <span className="workflow-run-detail">{detail}</span>}
                </span>
              </div>
              <span className="workflow-run-state">{state.label}</span>
              <div className="workflow-run-count">
                {node.total > 0 ? (
                  <span>
                    {node.done} / {node.total}
                  </span>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
                {active && node.total > 0 && (
                  <progress aria-label={`Progresso de ${node.label}`} value={pct} max={100} />
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
