import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { workflowPeriod, type WorkflowOptions } from "@/services/scheduled-workflow";
import { workflowCatalog } from "./catalog";
import type { CargoNode } from "./workflow-node";

interface Props {
  node: CargoNode | undefined;
  onOptions(options: WorkflowOptions): void;
  onRemove(): void;
}
export function NodeSettings({ node, onOptions, onRemove }: Props) {
  if (!node)
    return (
      <aside className="workflow-settings">
        <p className="text-sm text-muted-foreground">Selecione uma etapa</p>
      </aside>
    );
  const { label, icon: Icon } = workflowCatalog[node.data.kind];
  const options = node.data.options;
  const query = node.data.kind === "sql" || node.data.kind === "novelis_report";
  return (
    <aside className="workflow-settings space-y-5">
      <div className="flex items-center gap-2 text-sm font-medium">
        <Icon className="h-4 w-4" />
        {label}
      </div>
      {query && (
        <>
          <div className="space-y-1.5">
            <Label htmlFor="workflow-period-start">De quantos dias atrás</Label>
            <Input
              id="workflow-period-start"
              type="number"
              min={0}
              max={30}
              value={options.start_days_ago}
              onChange={(event) =>
                onOptions({ ...options, start_days_ago: Number(event.target.value) })
              }
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="workflow-period-end">Até quantos dias atrás</Label>
            <Input
              id="workflow-period-end"
              type="number"
              min={0}
              max={30}
              value={options.end_days_ago}
              onChange={(event) =>
                onOptions({ ...options, end_days_ago: Number(event.target.value) })
              }
            />
          </div>
          <p className="text-xs text-muted-foreground">{workflowPeriod(options)}</p>
        </>
      )}
      {node.data.kind === "tickets" && (
        <p className="text-xs text-muted-foreground">
          Abertura por HTTP com os documentos conferidos.
        </p>
      )}
      {node.data.kind === "tariffs" && (
        <p className="text-xs text-muted-foreground">
          Atualiza o catálogo pelo portal e aguarda a conclusão.
        </p>
      )}
      {node.data.kind === "generate_report" && (
        <p className="text-xs text-muted-foreground">
          Atualiza o Excel diário com as aberturas confirmadas.
        </p>
      )}
      {node.data.kind === "open_report" && (
        <p className="text-xs text-muted-foreground">
          Abre o relatório na tela de Relatórios diários ao concluir.
        </p>
      )}
      {node.data.kind === "completion_modal" && (
        <p className="text-xs text-muted-foreground">
          Mostra o resultado da execução ao finalizar.
        </p>
      )}
      <Button
        type="button"
        size="sm"
        variant="outline"
        className="text-destructive"
        onClick={onRemove}
      >
        <Trash2 className="h-4 w-4" />
        Excluir etapa
      </Button>
    </aside>
  );
}
