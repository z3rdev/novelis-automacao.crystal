import { expect, it } from "vitest";
import { emptySchedule } from "./schedule-options";
import { schedulePolicy, schedulePolicyError, scheduleTimes } from "./schedule-policy";

it("mantém o comportamento diário dos agendamentos antigos", () => {
  const old = emptySchedule();
  delete old.runs_per_day;
  delete old.interval_minutes;
  delete old.max_retries;
  delete old.retry_interval_minutes;
  expect(schedulePolicy(old)).toEqual({
    runs_per_day: 1,
    interval_minutes: 60,
    max_retries: 0,
    retry_interval_minutes: 5,
  });
  expect(scheduleTimes(old)).toEqual(["08:00"]);
});

it("mostra os horários previstos e rejeita repetições que ultrapassam o dia", () => {
  const value = { ...emptySchedule(), runs_per_day: 3, interval_minutes: 120, max_retries: 2 };
  expect(scheduleTimes(value)).toEqual(["08:00", "10:00", "12:00"]);
  expect(schedulePolicyError({ ...value, time: "22:00" })).toContain("meia-noite");
  expect(schedulePolicyError({ ...value, max_retries: 11 })).toContain("quantidade");
});
