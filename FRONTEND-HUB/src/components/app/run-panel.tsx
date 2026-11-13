import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Progress } from "@/components/ui/progress";
import { useApi, type RunStatus } from "@/services";
import { RunPill, stageLabel, flowLabel } from "./status";
import { fmtDateTime } from "@/lib/format";
import { toast } from "sonner";
import "./run-panel.css";

export function useRun() {
  const { api, mode, baseUrl } = useApi();
  return useQuery({ queryKey: ["run", mode, baseUrl], queryFn: () => api.getRun(), refetchInterval: (q) => (q.state.data?.state === "executando" || q.state.data?.state === "parando" ? 800 : 4000), retry: 0 });
}

export function useRunActions() {
  const { api, mode, baseUrl } = useApi();
  const qc = useQueryClient();
  const key = ["run", mode, baseUrl];
  const inv = () => qc.invalidateQueries();
  const start = useMutation({ mutationFn: api.startRun, onSuccess: () => { toast.success("Execução iniciada"); inv(); }, onError: (e: Error) => toast.error(e.message) });
  const stop = useMutation({
    mutationFn: () => api.stopRun(),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: key });
      const previous = qc.getQueryData<RunStatus>(key);
      qc.setQueryData<RunStatus>(key, (value) => value ? { ...value, state: "parando", stages: value.stages.map((stage) => stage.state === "executando" ? { ...stage, state: "parando" } : stage) } : value);
      return { previous };
    },
    onSuccess: (value) => { qc.setQueryData(key, value); toast.warning(value.state === "cancelada" ? "Execução cancelada" : "Encerrando as tarefas em andamento…"); },
    onError: (e: Error, _request, context) => { if (context?.previous) qc.setQueryData(key, context.previous); toast.error(e.message); },
    onSettled: inv,
  });
  return { start, stop };
}

export const isBusy = (r?: RunStatus) => r?.state === "executando" || r?.state === "parando";

export { StagesView } from "./stage-progress";

export function RunSummary({ run }: { run: RunStatus }) {
  const pct = run.total ? Math.round((run.processados / run.total) * 100) : run.state === "concluida" ? 100 : 0;
  return (
    <div className="run-summary"><div className="run-summary-grid text-sm">
      <div><div className="text-xs text-muted-foreground">Situação</div><div className="mt-1"><RunPill s={run.state} /></div></div>
      <div><div className="text-xs text-muted-foreground">Etapa atual</div><div className="mt-1 font-medium">{run.etapaAtual ? stageLabel[run.etapaAtual] : "—"}</div></div>
      <div><div className="text-xs text-muted-foreground">CT-e atual</div><div className="mt-1 font-mono font-medium">{run.cteAtual ?? "—"}</div></div>
      <div><div className="text-xs text-muted-foreground">Fluxo · início</div><div className="mt-1 font-medium" title={run.flow ? flowLabel[run.flow] : ""}>{run.flow ? flowLabel[run.flow].split(" (")[0] : "—"}</div><div className="text-xs text-muted-foreground">{fmtDateTime(run.iniciadoEm)}</div></div>
      <div><div className="text-xs text-muted-foreground">Processados no lote</div><div className="mt-1 font-semibold tabular-nums">{run.processados} / {run.total}</div><Progress value={pct} className="mt-1 h-1.5" /></div>
    </div></div>
  );
}
