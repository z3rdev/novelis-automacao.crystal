import { useEffect, useRef, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { FileSpreadsheet, CheckCircle2, AlertTriangle } from "lucide-react";
import { useApi, type RunStatus } from "@/services";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { fmtDateTime } from "@/lib/format";
import { useAppDialogs } from "../app-dialogs";
import { useRun } from "../run-panel";
import { RunPill } from "../status";

export function WorkflowCompletionMonitor() {
  const { mode, baseUrl } = useApi();
  const { data: run } = useRun();
  const navigate = useNavigate();
  const dialogs = useAppDialogs();
  const [completed, setCompleted] = useState<RunStatus | null>(null);
  const handled = useRef(new Set<string>());
  const actions = run?.workflow?.completion;
  const busy = dialogs.active && dialogs.active !== "workflow-completion";

  useEffect(() => {
    if (
      mode !== "local" ||
      !run?.id ||
      !actions?.ready ||
      busy ||
      !["concluida", "falhou", "cancelada"].includes(run.state)
    )
      return;
    const key = `cargo-hub.workflow-completion.${baseUrl}.${run.id}`;
    if (handled.current.has(key) || localStorage.getItem(key)) return;
    handled.current.add(key);
    localStorage.setItem(key, "1");
    if (actions.open_report && actions.report_id && !actions.show_modal) {
      void navigate({ to: "/relatorios", search: { report: actions.report_id } });
    }
    if (actions.show_modal) {
      setCompleted(run);
      dialogs.show("workflow-completion");
    }
  }, [run, actions, mode, baseUrl, busy, dialogs, navigate]);

  const result = completed?.workflow?.completion;
  const success = completed?.state === "concluida" && !result?.error;
  const close = (showReport = result?.open_report ?? false) => {
    if (showReport && result?.report_id)
      void navigate({ to: "/relatorios", search: { report: result.report_id } });
    dialogs.hide("workflow-completion");
    setCompleted(null);
  };
  return (
    <Dialog
      open={dialogs.active === "workflow-completion" && !!completed}
      onOpenChange={(open) => !open && close()}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {success ? (
              <CheckCircle2 className="h-5 w-5 text-success" />
            ) : (
              <AlertTriangle className="h-5 w-5 text-warning-foreground" />
            )}
            {success ? "Fluxo concluído" : "Fluxo finalizado"}
          </DialogTitle>
          <DialogDescription>{completed?.workflow?.name}</DialogDescription>
        </DialogHeader>
        {completed && (
          <div className="space-y-4">
            <RunPill s={completed.state} />
            <div className="grid grid-cols-2 gap-3 rounded-md border p-3 text-sm">
              <div>
                <p className="text-xs text-muted-foreground">Chamados abertos</p>
                <p className="mt-1 text-lg tabular-nums">{result?.opened_count ?? 0}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Etapas concluídas</p>
                <p className="mt-1 text-lg tabular-nums">
                  {completed.workflow?.completed} / {completed.workflow?.total}
                </p>
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              Finalizado em {fmtDateTime(completed.finalizadoEm)}
            </p>
            {result?.error && (
              <p role="alert" className="text-sm text-warning-foreground">
                {result.error}
              </p>
            )}
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => close()}>
                Fechar
              </Button>
              {result?.report_id && (
                <Button
                  onClick={() => {
                    close(true);
                  }}
                >
                  <FileSpreadsheet />
                  Ver relatório
                </Button>
              )}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
