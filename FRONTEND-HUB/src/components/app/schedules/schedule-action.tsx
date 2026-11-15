import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { scheduleFlows } from "@/services/schedule-options";
import type { ScheduleInput } from "@/services";
import { FluentIcon } from "../fluent-icon";
import type { ScheduleFieldsProps } from "./form-types";
import { AppSelect } from "../fields/app-select";

export function ScheduleAction({
  value,
  onChange,
  onEditFlow,
}: ScheduleFieldsProps & { onEditFlow(): void }) {
  const mode =
    value.flow === "completo" ? "full" : value.flow === "personalizado" ? "custom" : "single";
  const choices = [
    {
      id: "full",
      title: "Fluxo completo",
      detail: "Todas as etapas em sequência, da consulta ao relatório de chamados.",
    },
    {
      id: "single",
      title: "Uma etapa só",
      detail: "Útil para repetir uma parte do processo ao longo do dia.",
    },
    {
      id: "custom",
      title: "Fluxo personalizado",
      detail: "Uma sequência de etapas montada por você.",
    },
  ];
  return (
    <section className="schedule-form-section" aria-labelledby="schedule-action-title">
      <h2 id="schedule-action-title">O que executar</h2>
      <div className="schedule-surface">
        {choices.map((choice) => (
          <div key={choice.id} className="schedule-choice" data-selected={mode === choice.id}>
            <label className="schedule-choice-label">
              <input
                type="radio"
                name="schedule-action"
                checked={mode === choice.id}
                onChange={() =>
                  onChange({
                    ...value,
                    flow:
                      choice.id === "full"
                        ? "completo"
                        : choice.id === "custom"
                          ? "personalizado"
                          : mode === "single"
                            ? value.flow
                            : "consulta",
                  })
                }
              />
              <span>
                <span className="font-medium">{choice.title}</span>
                <span className="schedule-choice-description">{choice.detail}</span>
              </span>
            </label>
            {mode === "single" && choice.id === "single" && (
              <div className="schedule-choice-detail">
                <Label htmlFor="schedule-flow" className="sr-only">
                  Etapa
                </Label>
                <AppSelect
                  label="Etapa"
                  id="schedule-flow"
                  className="schedule-step-select"
                  value={value.flow}
                  onValueChange={(flow) =>
                    onChange({ ...value, flow: flow as ScheduleInput["flow"] })
                  }
                  options={Object.entries(scheduleFlows)
                    .filter(([key]) => !["completo", "personalizado"].includes(key))
                    .map(([key, label]) => ({ value: key, label }))}
                />
              </div>
            )}
            {mode === "custom" && choice.id === "custom" && (
              <div className="schedule-choice-detail">
                <div className="schedule-flow-summary">
                  <FluentIcon name="list" />
                  <div>
                    <span className="font-medium">
                      {value.workflow?.name ?? "Nenhum fluxo criado"}
                    </span>
                    <p>
                      {value.workflow
                        ? `${value.workflow.nodes.length} etapas`
                        : "Monte a sequência da rotina."}
                    </p>
                  </div>
                  <Button type="button" size="sm" variant="outline" onClick={onEditFlow}>
                    {value.workflow ? "Editar fluxo" : "Criar fluxo personalizado"}
                  </Button>
                </div>
              </div>
            )}
          </div>
        ))}
        {mode !== "custom" && (
          <div className="schedule-setting-row">
            <div>
              <Label htmlFor="schedule-period">Dias anteriores incluídos</Label>
              <p>0 consulta hoje. Máximo: 30 dias anteriores.</p>
            </div>
            <Input
              id="schedule-period"
              className="schedule-number"
              type="number"
              min={0}
              max={30}
              required
              value={value.days_back}
              onChange={(event) => onChange({ ...value, days_back: Number(event.target.value) })}
            />
          </div>
        )}
      </div>
    </section>
  );
}
