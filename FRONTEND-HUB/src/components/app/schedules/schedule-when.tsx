import { useState } from "react";
import { AppTimePicker } from "../fields/app-time-picker";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { fullWeekdays, weekdayNames } from "@/services/schedule-options";
import { ScheduleRecurrence } from "../schedule-recurrence";
import type { ScheduleFieldsProps } from "./form-types";

export function ScheduleWhen({ value, onChange }: ScheduleFieldsProps) {
  const [choose, setChoose] = useState(
    value.weekdays.length !== 7 && value.weekdays.join() !== "0,1,2,3,4",
  );
  const preset = choose ? "choose" : value.weekdays.length === 7 ? "all" : "work";
  return (
    <section className="schedule-form-section" aria-labelledby="schedule-when-title">
      <h2 id="schedule-when-title">Quando</h2>
      <div className="schedule-surface">
        <div className="schedule-setting-row">
          <div>
            <Label htmlFor="schedule-time">Horário de início</Label>
            <p>Horário local deste computador.</p>
          </div>
          <AppTimePicker
            label="Horário de início"
            id="schedule-time"
            className="schedule-time-input"
            value={value.time}
            onChange={(time) => onChange({ ...value, time })}
          />
        </div>
        <div className="schedule-setting-row schedule-days-row">
          <div>
            <Label>Dias</Label>
            <p>
              Roda:{" "}
              {value.weekdays.length
                ? value.weekdays.map((day) => fullWeekdays[day]).join(", ")
                : "selecione ao menos um dia"}
              .
            </p>
          </div>
          <div className="schedule-day-presets" aria-label="Seleção de dias">
            {[
              ["all", "Todos os dias"],
              ["work", "Dias úteis"],
              ["choose", "Escolher"],
            ].map(([key, label]) => (
              <Button
                key={key}
                type="button"
                size="sm"
                variant="ghost"
                aria-pressed={preset === key}
                onClick={() => {
                  setChoose(key === "choose");
                  if (key !== "choose")
                    onChange({
                      ...value,
                      weekdays: key === "all" ? [0, 1, 2, 3, 4, 5, 6] : [0, 1, 2, 3, 4],
                    });
                }}
              >
                {label}
              </Button>
            ))}
          </div>
          {choose && (
            <div className="schedule-weekdays">
              {weekdayNames.map((label, day) => (
                <Button
                  key={day}
                  type="button"
                  size="sm"
                  variant="outline"
                  aria-pressed={value.weekdays.includes(day)}
                  onClick={() =>
                    onChange({
                      ...value,
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
          )}
          {!value.weekdays.length && (
            <p className="text-xs text-destructive">Selecione ao menos um dia.</p>
          )}
        </div>
        <ScheduleRecurrence value={value} onChange={onChange} />
      </div>
    </section>
  );
}
