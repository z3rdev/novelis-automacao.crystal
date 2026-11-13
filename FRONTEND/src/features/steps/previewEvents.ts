import type { StepDefinition } from "../../lib/api";

export interface StepEventPayload {
  step?: unknown;
  inputValue?: unknown;
}

export interface RunStartPayload {
  flow?: string;
  dry_run?: boolean;
  sample_filial?: string;
  sample_serie?: string;
  sample_documento?: string;
  sample_cte?: string;
}

export type PreviewCommand =
  | {
      type: "preview.click";
      x: number;
      y: number;
      viewportWidth: number;
      viewportHeight: number;
    }
  | { type: "preview.type"; text: string }
  | { type: "preview.set_value"; selector: string; text: string }
  | { type: "preview.dellmar_login" };

export function isStepDefinition(value: unknown): value is StepDefinition {
  if (!value || typeof value !== "object") return false;
  const step = value as StepDefinition;
  return (
    typeof step.number === "number" &&
    typeof step.label === "string" &&
    typeof step.action === "string" &&
    typeof step.x === "number" &&
    typeof step.y === "number" &&
    Boolean(step.viewport)
  );
}
