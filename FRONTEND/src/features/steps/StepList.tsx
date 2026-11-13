import { ListChecks } from "lucide-react";

import type { StepDefinition } from "../../lib/api";

interface Props {
  steps: StepDefinition[];
  selected?: StepDefinition | null;
  currentStep?: number | null;
  onSelect: (step: StepDefinition) => void;
}

export function StepList({ steps, selected, currentStep, onSelect }: Props) {
  return (
    <section className="panel step-list-panel">
      <div className="panel-title">
        <ListChecks size={18} aria-hidden="true" />
        <h2>Passos</h2>
        <span className="pill">{steps.length}</span>
      </div>
      <div className="step-list">
        {steps.map((step) => {
          const active = selected?.number === step.number;
          const running = currentStep === step.number;
          return (
            <button
              className={`step-row ${active ? "selected" : ""} ${running ? "running" : ""}`}
              key={step.number}
              onClick={() => onSelect(step)}
              type="button"
            >
              <span>{String(step.number).padStart(2, "0")}</span>
              <strong>{step.label}</strong>
              <small>{step.action}</small>
            </button>
          );
        })}
      </div>
    </section>
  );
}
