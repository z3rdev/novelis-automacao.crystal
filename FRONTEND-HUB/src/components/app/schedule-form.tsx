import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { workflowError } from "@/services/scheduled-workflow";
import { schedulePolicyError } from "@/services/schedule-policy";
import { WorkflowEditor } from "./workflow/workflow-editor";
import { ScheduleRetry } from "./schedule-recurrence";
import { ScheduleWhen } from "./schedules/schedule-when";
import { ScheduleAction } from "./schedules/schedule-action";
import { FluentIcon } from "./fluent-icon";
import type { ScheduleFieldsProps } from "./schedules/form-types";
import "./schedules/schedules.css";

interface Props extends ScheduleFieldsProps {
  onSave(): void;
  onCancel(): void;
  onRemove?: (() => void) | undefined;
  saving: boolean;
  editing: boolean;
}

export function ScheduleForm({
  value,
  onChange,
  onSave,
  onCancel,
  onRemove,
  saving,
  editing,
}: Props) {
  const [editor, setEditor] = useState(false);
  const error =
    schedulePolicyError(value) ||
    (value.flow === "personalizado"
      ? value.workflow
        ? workflowError(value.workflow)
        : "Crie o fluxo do agendamento."
      : null);
  return (
    <form
      className="schedule-form"
      onSubmit={(event) => {
        event.preventDefault();
        if (!error && value.weekdays.length && value.name.trim().length >= 2) onSave();
      }}
    >
      <div className="schedule-surface">
        <div className="schedule-setting-row">
          <div>
            <Label htmlFor="schedule-name">Nome</Label>
            <p>Como a rotina aparece na lista e nas notificações.</p>
          </div>
          <Input
            id="schedule-name"
            aria-label="Nome do agendamento"
            className="schedule-name-input"
            value={value.name}
            onChange={(event) => onChange({ ...value, name: event.target.value })}
            maxLength={100}
            minLength={2}
            required
          />
        </div>
      </div>
      <ScheduleWhen value={value} onChange={onChange} />
      <ScheduleAction value={value} onChange={onChange} onEditFlow={() => setEditor(true)} />
      <ScheduleRetry value={value} onChange={onChange} />
      {error && (
        <p role="alert" className="schedule-error">
          {error}
        </p>
      )}
      <footer className="schedule-form-footer">
        {editing && onRemove && (
          <Button
            type="button"
            variant="ghost"
            className="text-destructive"
            onClick={onRemove}
            disabled={saving}
          >
            <FluentIcon name="cancel" />
            Excluir rotina
          </Button>
        )}
        <div>
          <Button type="button" variant="outline" onClick={onCancel} disabled={saving}>
            Cancelar
          </Button>
          <Button
            type="submit"
            disabled={saving || !value.weekdays.length || value.name.trim().length < 2 || !!error}
          >
            {saving ? "Salvando…" : "Salvar"}
          </Button>
        </div>
      </footer>
      {editor && (
        <WorkflowEditor
          initial={value.workflow ?? null}
          days={value.days_back}
          onClose={() => setEditor(false)}
          onSave={(workflow) => {
            onChange({ ...value, flow: "personalizado", workflow });
            setEditor(false);
          }}
        />
      )}
    </form>
  );
}
