import type { StageState } from "./types";
import type { WorkflowKind, WorkflowOptions } from "./scheduled-workflow";

export interface WorkflowNodeProgress {
  id: string;
  kind: WorkflowKind;
  label: string;
  options: WorkflowOptions;
  state: StageState;
  done: number;
  total: number;
  detail: string;
  started_at: string | null;
  finished_at: string | null;
}
export interface WorkflowCompletion {
  ready: boolean;
  open_report: boolean;
  show_modal: boolean;
  report_id: string | null;
  report_date: string | null;
  opened_count: number;
  existing_count: number;
  error: string | null;
}
export interface WorkflowRun {
  name: string;
  current_node_id: string | null;
  nodes: WorkflowNodeProgress[];
  completed: number;
  total: number;
  completion: WorkflowCompletion | null;
}
