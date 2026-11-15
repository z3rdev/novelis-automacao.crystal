import { RefreshCw, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { RunStatus } from "@/services";
import { isBusy, useRunActions } from "./run-panel";

export function OverviewConsultAction({
  run,
  refreshing,
  invalid,
  onConsult,
}: {
  run: RunStatus | undefined;
  refreshing: boolean;
  invalid: boolean;
  onConsult(): void;
}) {
  const { stop } = useRunActions();
  const stopping = stop.isPending || run?.state === "parando";
  if (isBusy(run) || stopping) {
    return (
      <Button variant="destructive" size="sm" disabled={stopping} onClick={() => stop.mutate()}>
        <Square />
        {stopping ? "Parando…" : "Parar automação"}
      </Button>
    );
  }
  return (
    <Button variant="outline" size="sm" onClick={onConsult} disabled={refreshing || invalid}>
      <RefreshCw className={refreshing ? "animate-spin" : ""} />
      {refreshing ? "Iniciando consulta…" : "Consultar agora"}
    </Button>
  );
}
