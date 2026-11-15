import { schedulePolicy, scheduleTimes } from "@/services/schedule-policy";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { ScheduleFieldsProps } from "./schedules/form-types";

export function ScheduleRecurrence({ value, onChange }: ScheduleFieldsProps) {
  const policy = schedulePolicy(value);
  const times = scheduleTimes(value);
  const shown = times.length > 6 ? [...times.slice(0, 5), "…", times.at(-1)] : times;
  return (
    <div className="schedule-setting-row">
      <div>
        <Label htmlFor="schedule-runs_per_day">Repetir no mesmo dia</Label>
        <p title={times.join(" · ")}>
          Horários previstos: {shown.join(" · ") || "confira os horários"}
        </p>
      </div>
      <div className="schedule-inline-controls">
        <Input
          id="schedule-runs_per_day"
          aria-label="Execuções por dia"
          className="schedule-number"
          type="number"
          min={1}
          max={48}
          step={1}
          required
          value={policy.runs_per_day}
          onChange={(event) => onChange({ ...value, runs_per_day: Number(event.target.value) })}
        />
        <span>vez{policy.runs_per_day === 1 ? "" : "es"} por dia, a cada</span>
        <Input
          aria-label="Intervalo entre execuções (min)"
          className="schedule-number"
          type="number"
          min={1}
          max={1440}
          step={1}
          required
          disabled={policy.runs_per_day === 1}
          value={policy.interval_minutes}
          onChange={(event) => onChange({ ...value, interval_minutes: Number(event.target.value) })}
        />
        <span>min</span>
      </div>
    </div>
  );
}

export function ScheduleRetry({ value, onChange }: ScheduleFieldsProps) {
  const policy = schedulePolicy(value);
  return (
    <section className="schedule-form-section" aria-labelledby="schedule-retry-title">
      <h2 id="schedule-retry-title">Se falhar</h2>
      <div className="schedule-surface">
        <div className="schedule-setting-row">
          <div>
            <Label htmlFor="schedule-max_retries">Tentar novamente</Label>
            <p>
              {policy.max_retries
                ? `Até ${policy.max_retries + 1} tentativas por horário.`
                : "Desligado. Se falhar, a rotina só roda de novo no próximo horário."}
            </p>
          </div>
          <div className="schedule-inline-controls">
            <Input
              id="schedule-max_retries"
              aria-label="Novas tentativas após falha"
              className="schedule-number"
              type="number"
              min={0}
              max={10}
              step={1}
              required
              value={policy.max_retries}
              onChange={(event) => onChange({ ...value, max_retries: Number(event.target.value) })}
            />
            <span>vezes, esperando</span>
            <Input
              aria-label="Espera entre tentativas (min)"
              className="schedule-number"
              type="number"
              min={1}
              max={1440}
              step={1}
              required
              disabled={policy.max_retries === 0}
              value={policy.retry_interval_minutes}
              onChange={(event) =>
                onChange({ ...value, retry_interval_minutes: Number(event.target.value) })
              }
            />
            <span>min</span>
          </div>
        </div>
      </div>
    </section>
  );
}
