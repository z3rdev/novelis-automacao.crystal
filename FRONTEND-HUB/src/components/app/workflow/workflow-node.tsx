import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import { cn } from "@/lib/utils";
import {
  workflowPeriod,
  type WorkflowKind,
  type WorkflowOptions,
} from "@/services/scheduled-workflow";
import { workflowCatalog } from "./catalog";

export type CargoNode = Node<{ kind: WorkflowKind; options: WorkflowOptions }, "cargo">;

export function WorkflowCard({ data, selected }: NodeProps<CargoNode>) {
  const { icon: Icon, label, group } = workflowCatalog[data.kind];
  const query = data.kind === "sql" || data.kind === "novelis_report";
  return (
    <div className={cn("workflow-card", selected && "is-selected")}>
      <Handle type="target" position={Position.Left} />
      <div className="flex items-center gap-2.5">
        <span className="rounded-md bg-primary/5 p-2 text-primary">
          <Icon className="h-5 w-5" />
        </span>
        <div className="min-w-0">
          <span className="text-[10px] text-muted-foreground">{group}</span>
          <p className="text-xs font-medium leading-5">{label}</p>
        </div>
      </div>
      {query && (
        <p className="mt-2 border-t pt-2 text-[10px] text-muted-foreground">
          {workflowPeriod(data.options)}
        </p>
      )}
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
