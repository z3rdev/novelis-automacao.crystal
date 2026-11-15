import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useApi, type AutomationSchedule } from "@/services";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { fmtDateTime } from "@/lib/format";
import { scheduleStates } from "@/services/schedule-options";
import { FluentIcon } from "../fluent-icon";

export function ScheduleHistory({
  value,
  onClose,
}: {
  value: AutomationSchedule;
  onClose(): void;
}) {
  const { api, mode, baseUrl } = useApi();
  const [page, setPage] = useState(0);
  const query = useQuery({
    queryKey: ["schedule-history", mode, baseUrl, value.id, page],
    queryFn: () => api.getScheduleHistory(value.id, page),
    retry: 0,
    refetchInterval: 15000,
  });
  return (
    <Sheet
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <SheetContent className="w-full overflow-y-auto sm:max-w-xl p-0">
        <SheetHeader className="border-b px-6 py-5 pr-12">
          <SheetTitle>Histórico de execuções</SheetTitle>
          <SheetDescription>{value.name}</SheetDescription>
        </SheetHeader>
        <div className="p-6 space-y-4">
          {query.isPending && (
            <p className="text-sm text-muted-foreground">Carregando histórico…</p>
          )}
          {query.isError && (
            <p role="alert" className="text-sm text-destructive">
              {query.error.message}
            </p>
          )}
          {query.data?.rows.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Esta rotina ainda não possui execuções registradas.
            </p>
          )}
          {query.data?.rows.map((row) => (
            <article
              key={`${row.local_date}-${row.slot}-${row.attempt}`}
              className="border-b pb-4 space-y-2 text-sm"
            >
              <div className="flex items-center justify-between gap-3">
                <span className="schedule-result" data-state={row.state}>
                  <FluentIcon
                    name={
                      row.state === "completed"
                        ? "check"
                        : row.state === "failed"
                          ? "error"
                          : "clock"
                    }
                  />
                  {scheduleStates[row.state] ?? row.state}
                </span>
                <span className="text-xs text-muted-foreground">
                  Horário {row.slot + 1} · Tentativa {row.attempt + 1}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                {row.started_at
                  ? `Início: ${fmtDateTime(row.started_at)}`
                  : `Prevista: ${fmtDateTime(row.due_at)}`}
                {row.finished_at && ` · Fim: ${fmtDateTime(row.finished_at)}`}
              </p>
              <p className="break-words">{row.message}</p>
            </article>
          ))}
          {!!query.data?.total && (
            <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
              <span>
                {query.data.total} registros · Página {page + 1}
              </span>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={!page}
                  onClick={() => setPage(page - 1)}
                >
                  Anterior
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={(page + 1) * query.data.page_size >= query.data.total}
                  onClick={() => setPage(page + 1)}
                >
                  Próxima
                </Button>
              </div>
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
