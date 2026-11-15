import type { AutomationSchedule } from "@/services";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { MoreHorizontal } from "lucide-react";
import {
  weekdaySummary,
  scheduleDate,
  scheduleRemaining,
  scheduleFlows,
  scheduleStates,
} from "@/services/schedule-options";
import { FluentIcon } from "../fluent-icon";

interface Props {
  values: AutomationSchedule[];
  busy: boolean;
  starting?: string | undefined;
  toggling: boolean;
  onStart(value: AutomationSchedule): void;
  onToggle(value: AutomationSchedule): void;
  onEdit(value: AutomationSchedule): void;
  onDuplicate(value: AutomationSchedule): void;
  onHistory(value: AutomationSchedule): void;
  onRemove(value: AutomationSchedule): void;
}

export function ScheduleList({
  values,
  busy,
  starting,
  toggling,
  onStart,
  onToggle,
  onEdit,
  onDuplicate,
  onHistory,
  onRemove,
}: Props) {
  return (
    <div className="schedule-table-wrap">
      <table className="schedule-table">
        <thead>
          <tr>
            <th>Horário</th>
            <th>Rotina</th>
            <th>Próxima execução</th>
            <th>Última execução</th>
            <th>Ativa</th>
            <th>
              <span className="sr-only">Ações</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {values.map((value) => {
            const last = value.last_run;
            const failed = last && ["failed", "interrupted"].includes(last.state);
            const exhausted =
              last?.state === "failed" &&
              !!value.max_retries &&
              (last.attempt ?? 0) >= value.max_retries;
            const duration =
              last?.finished_at && last.started_at
                ? Math.max(
                    0,
                    Math.round(
                      (Date.parse(last.finished_at) - Date.parse(last.started_at)) / 60000,
                    ),
                  )
                : null;
            return (
              <tr key={value.id} data-paused={!value.enabled}>
                <td className="schedule-hour">{value.time}</td>
                <td>
                  <span className="schedule-name">{value.name}</span>
                  <p className="schedule-description">
                    {weekdaySummary(value.weekdays)} ·{" "}
                    {value.flow === "personalizado"
                      ? `${value.workflow?.name ?? "Fluxo personalizado"} (${value.workflow?.nodes.length ?? 0} etapas)`
                      : scheduleFlows[value.flow]}
                  </p>
                  {(value.runs_per_day ?? 1) > 1 && (
                    <p>
                      {value.runs_per_day} vezes por dia · a cada {value.interval_minutes ?? 60} min
                    </p>
                  )}
                </td>
                <td>
                  {!value.enabled ? (
                    <>
                      <span className="text-muted-foreground">Pausada</span>
                      <p>Ative para voltar a rodar</p>
                    </>
                  ) : value.next_run_at ? (
                    <>
                      <span>{scheduleDate(value.next_run_at)}</span>
                      <p>{scheduleRemaining(value.next_run_at)}</p>
                      {(value.next_attempt ?? 1) > 1 && (
                        <p>
                          Nova tentativa {value.next_attempt} de {(value.max_retries ?? 0) + 1}
                        </p>
                      )}
                    </>
                  ) : (
                    <span className="text-muted-foreground">Sem horário previsto</span>
                  )}
                </td>
                <td>
                  {last ? (
                    <>
                      <span className="schedule-result" data-state={last.state}>
                        <FluentIcon
                          name={last.state === "completed" ? "check" : failed ? "error" : "clock"}
                        />
                        {exhausted
                          ? "Tentativas esgotadas"
                          : (scheduleStates[last.state] ?? last.state)}
                      </span>
                      <p>
                        {last.started_at ? scheduleDate(last.started_at) : "—"}
                        {duration !== null ? ` · ${duration || "<1"} min` : ""}
                        {failed && (
                          <>
                            {" "}
                            ·{" "}
                            <button
                              className="underline underline-offset-2 text-primary"
                              onClick={() => onHistory(value)}
                            >
                              Ver o que aconteceu
                            </button>
                          </>
                        )}
                      </p>
                    </>
                  ) : (
                    <span className="text-muted-foreground">Ainda não executada</span>
                  )}
                </td>
                <td>
                  <Switch
                    aria-label={`Ativar ${value.name}`}
                    checked={value.enabled}
                    disabled={toggling}
                    onCheckedChange={() => onToggle(value)}
                  />
                </td>
                <td>
                  <div className="schedule-row-actions">
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Iniciar rotina ${value.name}`}
                      title={busy ? "Aguarde a automação atual encerrar" : "Iniciar rotina"}
                      disabled={busy}
                      onClick={() => onStart(value)}
                    >
                      <FluentIcon
                        name={starting === value.id ? "refresh" : "play"}
                        className={starting === value.id ? "animate-spin" : ""}
                      />
                    </Button>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Mais ações de ${value.name}`}
                        >
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-56">
                        <DropdownMenuItem onSelect={() => onEdit(value)}>Editar</DropdownMenuItem>
                        <DropdownMenuItem onSelect={() => onDuplicate(value)}>
                          Duplicar
                        </DropdownMenuItem>
                        <DropdownMenuItem onSelect={() => onHistory(value)}>
                          Ver histórico de execuções
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          className="text-destructive focus:text-destructive"
                          onSelect={() => onRemove(value)}
                        >
                          Excluir…
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
