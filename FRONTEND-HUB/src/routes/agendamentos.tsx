import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { CalendarClock, Pencil, Plus, RefreshCw, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { useApi, type AutomationSchedule, type ScheduleInput } from "@/services";
import { PageBody, Section } from "@/components/app/page";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  ScheduleForm,
  emptySchedule,
  scheduleFlows,
  weekdayNames,
} from "@/components/app/schedule-form";
import { fmtDateTime } from "@/lib/format";

export const Route = createFileRoute("/agendamentos")({
  head: () => ({ meta: [{ title: "Agendamentos · Cargo Hub" }] }),
  component: Schedules,
});

const runLabels: Record<string, string> = {
  starting: "Iniciando",
  running: "Em execução",
  completed: "Concluído",
  failed: "Falhou",
  cancelled: "Cancelado",
  interrupted: "Interrompido",
};

function Schedules() {
  const { api, mode, baseUrl } = useApi();
  const qc = useQueryClient();
  const key = ["schedules", mode, baseUrl];
  const query = useQuery({
    queryKey: key,
    queryFn: () => api.getSchedules(),
    refetchInterval: 15000,
    retry: 0,
  });
  const [form, setForm] = useState<ScheduleInput | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [removing, setRemoving] = useState<AutomationSchedule | null>(null);
  const refresh = () => void qc.invalidateQueries({ queryKey: key });
  const error = (value: Error) => toast.error(value.message);
  const save = useMutation({
    mutationFn: () => (editing ? api.updateSchedule(editing, form!) : api.createSchedule(form!)),
    onSuccess: () => {
      setForm(null);
      setEditing(null);
      refresh();
      toast.success("Agendamento salvo.");
    },
    onError: error,
  });
  const toggle = useMutation({
    mutationFn: (value: AutomationSchedule) =>
      api.updateSchedule(value.id, { ...value, enabled: !value.enabled }),
    onSuccess: refresh,
    onError: error,
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.removeSchedule(id),
    onSuccess: () => {
      refresh();
      setRemoving(null);
      toast.success("Agendamento removido.");
    },
    onError: error,
  });
  return (
    <PageBody>
      <Section
        title="Agendamentos automáticos"
        actions={
          <Button
            onClick={() => {
              setEditing(null);
              setForm(emptySchedule());
            }}
            disabled={mode !== "local"}
          >
            <Plus />
            Novo agendamento
          </Button>
        }
      >
        <p className="text-sm text-muted-foreground">
          Horário local de{" "}
          <strong className="text-foreground">{query.data?.device ?? "este computador"}</strong>. A
          conta Windows e o backend devem estar ativos para executar os fluxos.
        </p>
        <p className="mt-2 text-xs text-muted-foreground">
          Cada agendamento inicia uma vez por dia selecionado. Se já houver uma execução, ele
          aguarda a liberação do backend.
        </p>
      </Section>
      {form && (
        <Section title={editing ? "Editar agendamento" : "Novo agendamento"}>
          <ScheduleForm
            value={form}
            onChange={setForm}
            onSave={() => save.mutate()}
            onCancel={() => {
              setForm(null);
              setEditing(null);
            }}
            saving={save.isPending}
            editing={Boolean(editing)}
          />
        </Section>
      )}
      <Section
        title="Rotinas deste computador"
        actions={
          <Button size="sm" variant="outline" onClick={() => void query.refetch()}>
            <RefreshCw className={query.isFetching ? "animate-spin" : ""} />
            Atualizar
          </Button>
        }
      >
        {query.isError && (
          <p role="alert" className="text-sm text-destructive">
            Não foi possível consultar os agendamentos no backend.
          </p>
        )}
        {query.data?.schedules.length === 0 && (
          <div className="py-8 text-center text-muted-foreground">
            <CalendarClock className="mx-auto mb-3 h-8 w-8" />
            <p className="text-sm">Nenhum agendamento cadastrado.</p>
          </div>
        )}
        {Boolean(query.data?.schedules.length) && (
          <div className="overflow-x-auto">
            <Table className="min-w-[800px]">
              <TableHeader>
                <TableRow>
                  <TableHead>Ativo</TableHead>
                  <TableHead>Rotina</TableHead>
                  <TableHead>Próxima execução</TableHead>
                  <TableHead>Último resultado</TableHead>
                  <TableHead className="text-right">Ações</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {query.data?.schedules.map((value) => (
                  <TableRow key={value.id}>
                    <TableCell>
                      <Switch
                        checked={value.enabled}
                        onCheckedChange={() => toggle.mutate(value)}
                        disabled={toggle.isPending}
                        aria-label={`Ativar ${value.name}`}
                      />
                    </TableCell>
                    <TableCell>
                      <p className="font-medium">{value.name}</p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {value.time} · {value.weekdays.map((day) => weekdayNames[day]).join(", ")}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {scheduleFlows[value.flow]} ·{" "}
                        {value.days_back ? `Desde ${value.days_back} dia(s) atrás` : "Dia atual"}
                      </p>
                      <p className="text-xs text-muted-foreground">{value.operator_name}</p>
                    </TableCell>
                    <TableCell className="whitespace-nowrap">
                      {!value.enabled
                        ? "Desativado"
                        : value.next_run_at && new Date(value.next_run_at).getTime() <= Date.now()
                          ? "Aguardando execução"
                          : value.next_run_at
                            ? fmtDateTime(value.next_run_at)
                            : "—"}
                    </TableCell>
                    <TableCell>
                      <p>
                        {value.last_run
                          ? (runLabels[value.last_run.state] ?? value.last_run.state)
                          : "Ainda não executado"}
                      </p>
                      {value.last_run && (
                        <p
                          className="max-w-64 text-xs text-muted-foreground"
                          title={value.last_run.message}
                        >
                          {fmtDateTime(value.last_run.started_at)}
                        </p>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Editar ${value.name}`}
                          onClick={() => {
                            setEditing(value.id);
                            setForm({
                              name: value.name,
                              time: value.time,
                              weekdays: [...value.weekdays],
                              flow: value.flow,
                              days_back: value.days_back,
                              enabled: value.enabled,
                            });
                          }}
                        >
                          <Pencil />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Remover ${value.name}`}
                          onClick={() => setRemoving(value)}
                        >
                          <Trash2 />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </Section>
      <AlertDialog
        open={Boolean(removing)}
        onOpenChange={(open) => {
          if (!open) setRemoving(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remover agendamento?</AlertDialogTitle>
            <AlertDialogDescription>
              A rotina {removing?.name} deixará de iniciar automaticamente.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => removing && remove.mutate(removing.id)}
              disabled={remove.isPending}
            >
              Remover
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </PageBody>
  );
}
