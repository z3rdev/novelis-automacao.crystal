import { Save, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import type { ScheduleInput } from "@/services";

export const weekdayNames = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];
export const scheduleFlows = {
  consulta: "Somente consulta e verificação",
  somente_pdf: "Somente baixar PDFs",
  completo: "Fluxo completo",
};
export const emptySchedule = (): ScheduleInput => ({
  name: "",
  time: "08:00",
  weekdays: [0, 1, 2, 3, 4, 5, 6],
  flow: "consulta",
  days_back: 0,
  enabled: true,
});

interface Props {
  value: ScheduleInput;
  onChange(value: ScheduleInput): void;
  onSave(): void;
  onCancel(): void;
  saving: boolean;
  editing: boolean;
}

export function ScheduleForm({ value, onChange, onSave, onCancel, saving, editing }: Props) {
  const patch = (changes: Partial<ScheduleInput>) => onChange({ ...value, ...changes });
  return (
    <form
      className="space-y-5"
      onSubmit={(event) => {
        event.preventDefault();
        onSave();
      }}
    >
      <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_160px]">
        <div className="space-y-1.5">
          <Label htmlFor="schedule-name">Nome do agendamento</Label>
          <Input
            id="schedule-name"
            value={value.name}
            onChange={(event) => patch({ name: event.target.value })}
            maxLength={100}
            minLength={2}
            placeholder="Consulta da manhã"
            required
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="schedule-time">Horário local</Label>
          <Input
            id="schedule-time"
            type="time"
            value={value.time}
            onChange={(event) => patch({ time: event.target.value })}
            required
          />
        </div>
      </div>
      <div className="space-y-2">
        <Label>Dias da semana</Label>
        <div className="flex flex-wrap gap-2">
          {weekdayNames.map((label, day) => (
            <Button
              key={day}
              type="button"
              size="sm"
              variant={value.weekdays.includes(day) ? "default" : "outline"}
              aria-pressed={value.weekdays.includes(day)}
              onClick={() =>
                patch({
                  weekdays: value.weekdays.includes(day)
                    ? value.weekdays.filter((item) => item !== day)
                    : [...value.weekdays, day].sort(),
                })
              }
            >
              {label}
            </Button>
          ))}
        </div>
        {!value.weekdays.length && (
          <p className="text-xs text-destructive">Selecione ao menos um dia.</p>
        )}
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="schedule-flow">Tipo de execução</Label>
          <select
            id="schedule-flow"
            className="h-10 w-full rounded-md border bg-background px-3 text-sm"
            value={value.flow}
            onChange={(event) => patch({ flow: event.target.value as ScheduleInput["flow"] })}
          >
            {Object.entries(scheduleFlows).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="schedule-period">Dias anteriores incluídos</Label>
          <Input
            id="schedule-period"
            type="number"
            min={0}
            max={89}
            value={value.days_back}
            onChange={(event) => patch({ days_back: Number(event.target.value) })}
            required
          />
          <p className="text-xs text-muted-foreground">
            0 consulta hoje. 2 inclui anteontem, ontem e hoje.
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Switch
          id="schedule-enabled"
          checked={value.enabled}
          onCheckedChange={(enabled) => patch({ enabled })}
        />
        <Label htmlFor="schedule-enabled">Agendamento ativo</Label>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button
          type="submit"
          disabled={saving || !value.weekdays.length || value.name.trim().length < 2}
        >
          <Save />
          {editing ? "Salvar alterações" : "Salvar agendamento"}
        </Button>
        <Button type="button" variant="outline" onClick={onCancel} disabled={saving}>
          <X />
          Cancelar
        </Button>
      </div>
    </form>
  );
}
