import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { useApi, type AutomationSchedule, type ScheduleInput } from "@/services";
import { PageBody } from "@/components/app/page";
import { Button } from "@/components/ui/button";
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
import { ScheduleForm } from "@/components/app/schedule-form";
import { emptySchedule, scheduleDraft } from "@/services/schedule-options";
import { isBusy, useRun } from "@/components/app/run-panel";
import { FluentIcon } from "@/components/app/fluent-icon";
import { ScheduleList } from "@/components/app/schedules/schedule-list";
import { ScheduleHistory } from "@/components/app/schedules/schedule-history";
import "@/components/app/schedules/schedules.css";

export const Route = createFileRoute("/agendamentos")({
  head: () => ({ meta: [{ title: "Agendamentos · Cargo Hub" }] }),
  component: Schedules,
});

export function Schedules() {
  const { api, mode, baseUrl } = useApi();
  const qc = useQueryClient();
  const run = useRun();
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
  const [history, setHistory] = useState<AutomationSchedule | null>(null);
  const [notice, setNotice] = useState(true);
  const closeForm = () => {
    setForm(null);
    setEditing(null);
  };
  const refresh = () => void qc.invalidateQueries({ queryKey: key });
  const error = (value: Error) => toast.error(value.message);
  const start = useMutation({
    mutationFn: (value: AutomationSchedule) => api.runSchedule(value.id),
    onSuccess: (value) => {
      qc.setQueryData(["run", mode, baseUrl], value);
      refresh();
      toast.success("Rotina iniciada. Acompanhe em Monitor ao vivo.");
    },
    onError: error,
  });
  const save = useMutation({
    mutationFn: () => (editing ? api.updateSchedule(editing, form!) : api.createSchedule(form!)),
    onSuccess: () => {
      closeForm();
      refresh();
      toast.success("Agendamento salvo.");
    },
    onError: error,
  });
  const toggle = useMutation({
    mutationFn: (value: AutomationSchedule) =>
      api.updateSchedule(value.id, { ...scheduleDraft(value), enabled: !value.enabled }),
    onSuccess: refresh,
    onError: error,
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.removeSchedule(id),
    onSuccess: () => {
      refresh();
      if (removing?.id === editing) closeForm();
      setRemoving(null);
      toast.success("Agendamento removido.");
    },
    onError: error,
  });
  const values = query.data?.schedules ?? [];
  return (
    <PageBody className={`schedules-page${form ? " schedule-edit-page" : ""}`}>
      <header className="schedules-heading">
        <div>
          {form && (
            <button
              className="mb-3 text-xs text-muted-foreground hover:text-foreground"
              onClick={closeForm}
            >
              ← Agendamentos
            </button>
          )}
          <h1>{form ? (editing ? "Editar rotina" : "Novo agendamento") : "Agendamentos"}</h1>
          {!form && (
            <p>
              Rotinas que rodam sozinhas neste computador (
              <strong className="text-foreground">{query.data?.device ?? "…"}</strong>).{" "}
              {values.filter((value) => value.enabled).length} de {values.length} ativas.
            </p>
          )}
        </div>
        {!form && (
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
        )}
      </header>
      {mode === "local" && query.data?.running === false && (
        <p role="alert" className="schedule-notice">
          Agendador inativo. Reinicie o Cargo Hub para ativar as rotinas.
        </p>
      )}
      {form ? (
        <ScheduleForm
          value={form}
          onChange={setForm}
          onSave={() => save.mutate()}
          onCancel={closeForm}
          saving={save.isPending}
          editing={!!editing}
          onRemove={
            editing
              ? () => setRemoving(values.find((value) => value.id === editing) ?? null)
              : undefined
          }
        />
      ) : (
        <>
          {notice && (
            <div className="schedule-notice">
              <FluentIcon name="help" />
              <p>
                <strong>O Cargo Hub precisa estar aberto para as rotinas rodarem.</strong> Ele pode
                ficar minimizado na bandeja do Windows. Se outra execução estiver em andamento, a
                rotina espera ela terminar.
              </p>
              <button
                aria-label="Fechar orientação de agendamentos"
                onClick={() => setNotice(false)}
              >
                <FluentIcon name="cancel" />
              </button>
            </div>
          )}
          {query.isError && (
            <p role="alert" className="text-sm text-destructive">
              Não foi possível consultar os agendamentos.{" "}
              <button className="underline" onClick={() => void query.refetch()}>
                Tentar novamente
              </button>
            </p>
          )}
          {query.isPending && <p className="text-sm text-muted-foreground">Carregando rotinas…</p>}
          {!!values.length && (
            <ScheduleList
              values={values}
              busy={mode !== "local" || !run.isSuccess || isBusy(run.data) || start.isPending}
              starting={start.isPending ? start.variables?.id : undefined}
              toggling={toggle.isPending}
              onStart={(value) => start.mutate(value)}
              onToggle={(value) => toggle.mutate(value)}
              onEdit={(value) => {
                setEditing(value.id);
                setForm(scheduleDraft(value));
              }}
              onDuplicate={(value) => {
                setEditing(null);
                setForm({
                  ...scheduleDraft(value),
                  name: `${value.name.slice(0, 92)} (cópia)`,
                  enabled: false,
                });
              }}
              onHistory={setHistory}
              onRemove={setRemoving}
            />
          )}
          {query.isSuccess && !values.length && (
            <div className="schedule-surface p-8 text-sm text-muted-foreground">
              Nenhum agendamento cadastrado.
            </div>
          )}
        </>
      )}
      {history && (
        <ScheduleHistory key={history.id} value={history} onClose={() => setHistory(null)} />
      )}
      <AlertDialog
        open={!!removing}
        onOpenChange={(open) => {
          if (!open) setRemoving(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Excluir rotina?</AlertDialogTitle>
            <AlertDialogDescription>
              A rotina {removing?.name} deixará de iniciar automaticamente.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              disabled={remove.isPending}
              onClick={(event) => {
                event.preventDefault();
                if (removing) remove.mutate(removing.id);
              }}
            >
              Excluir rotina
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </PageBody>
  );
}
