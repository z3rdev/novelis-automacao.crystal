import { useState } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ScheduleForm } from "./schedule-form";
import { emptySchedule } from "@/services/schedule-options";
import { selectOption } from "@/test/select-option";
import type { ScheduleInput } from "@/services";

beforeEach(() =>
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  ),
);
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function Form({ save }: { save: (value: ScheduleInput) => void }) {
  const [value, onChange] = useState({ ...emptySchedule(), name: "Consulta" });
  return (
    <ScheduleForm
      value={value}
      onChange={onChange}
      editing={false}
      saving={false}
      onCancel={vi.fn()}
      onSave={() => save(value)}
    />
  );
}

it("salva frequência e tentativas e mostra uma prévia dos horários", () => {
  const save = vi.fn();
  render(<Form save={save} />);
  expect(screen.getByLabelText("Intervalo entre execuções (min)")).toBeDisabled();
  expect(screen.getByLabelText("Espera entre tentativas (min)")).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Execuções por dia"), { target: { value: "3" } });
  fireEvent.change(screen.getByLabelText("Intervalo entre execuções (min)"), {
    target: { value: "120" },
  });
  fireEvent.change(screen.getByLabelText("Novas tentativas após falha"), {
    target: { value: "2" },
  });
  fireEvent.change(screen.getByLabelText("Espera entre tentativas (min)"), {
    target: { value: "7" },
  });
  expect(screen.getByText("Horários previstos: 08:00 · 10:00 · 12:00")).toBeInTheDocument();
  expect(screen.getByText("Até 3 tentativas por horário.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Salvar" }));
  expect(save.mock.calls[0]![0]).toMatchObject({
    runs_per_day: 3,
    interval_minutes: 120,
    max_retries: 2,
    retry_interval_minutes: 7,
  });
});

it("impede salvar horários diários inválidos", async () => {
  render(<Form save={vi.fn()} />);
  fireEvent.click(screen.getByLabelText("Horário de início"));
  await selectOption("Hora: Horário de início", "23");
  await selectOption("Minuto: Horário de início", "30");
  fireEvent.click(screen.getByRole("button", { name: "Concluir" }));
  fireEvent.change(screen.getByLabelText("Execuções por dia"), { target: { value: "2" } });
  expect(screen.getByRole("alert")).toHaveTextContent("meia-noite");
  expect(screen.getByRole("button", { name: "Salvar" })).toBeDisabled();
});
