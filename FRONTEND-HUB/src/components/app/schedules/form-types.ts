import type { ScheduleInput } from "@/services";

export interface ScheduleFieldsProps {
  value: ScheduleInput;
  onChange(value: ScheduleInput): void;
}
