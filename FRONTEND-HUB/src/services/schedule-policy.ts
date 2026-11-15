import type { ScheduleInput } from "./operator-features";

export function schedulePolicy(value: ScheduleInput) {
  return {
    runs_per_day: value.runs_per_day ?? 1,
    interval_minutes: value.interval_minutes ?? 60,
    max_retries: value.max_retries ?? 0,
    retry_interval_minutes: value.retry_interval_minutes ?? 5,
  };
}

export function schedulePolicyError(value: ScheduleInput): string | null {
  const policy = schedulePolicy(value);
  const limits = [
    [policy.runs_per_day, 1, 48],
    [policy.interval_minutes, 1, 1440],
    [policy.max_retries, 0, 10],
    [policy.retry_interval_minutes, 1, 1440],
  ];
  if (
    limits.some(
      ([number, min, max]) => !Number.isInteger(number) || number! < min! || number! > max!,
    )
  )
    return "Confira a quantidade e os intervalos das execuções.";
  if (!/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(value.time)) return "Informe um horário válido.";
  const [hours, minutes] = value.time.split(":").map(Number);
  if (hours! * 60 + minutes! + (policy.runs_per_day - 1) * policy.interval_minutes >= 1440)
    return "As execuções do dia devem ser iniciadas antes da meia-noite.";
  return null;
}

export function scheduleTimes(value: ScheduleInput) {
  if (schedulePolicyError(value)) return [];
  const { runs_per_day, interval_minutes } = schedulePolicy(value);
  const [hours, minutes] = value.time.split(":").map(Number);
  return Array.from({ length: runs_per_day }, (_, index) => {
    const total = hours! * 60 + minutes! + index * interval_minutes;
    return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
  });
}
