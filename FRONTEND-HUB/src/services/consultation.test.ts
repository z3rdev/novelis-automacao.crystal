import { afterEach, describe, expect, it, vi } from "vitest";
import { dateLimits, periodError } from "./consultation";
afterEach(() => vi.useRealTimers());
describe("Intervalo personalizado", () => {
  it("limita o calendário a 30 dias atrás e rejeita intervalo invertido ou incompleto", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 10, 14, 12));
    expect(dateLimits()).toEqual({ min: "2026-10-15", max: "2026-11-14" });
    expect(periodError({ dataInicio: "2026-10-15", dataFim: "2026-11-12" })).toBeNull();
    expect(periodError({ dataInicio: "2026-10-14", dataFim: "2026-11-12" })).not.toBeNull();
    expect(periodError({ dataInicio: "2026-11-14", dataFim: "2026-11-15" })).not.toBeNull();
    expect(periodError({ dataInicio: "2026-11-14", dataFim: "2026-11-10" })).not.toBeNull();
    expect(periodError({ dataInicio: "", dataFim: "2026-11-14" })).not.toBeNull();
  });
});
