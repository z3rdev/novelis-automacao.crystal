import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { AutomationSchedule, RunStatus } from "@/services";
import { Schedules } from "@/routes/agendamentos";

const fixture = vi.hoisted(() => ({
  api: {
    getSchedules: vi.fn(),
    getRun: vi.fn(),
    runSchedule: vi.fn(),
    getScheduleHistory: vi.fn(),
    createSchedule: vi.fn(),
  },
}));
vi.mock("@/services", () => ({
  useApi: () => ({ api: fixture.api, mode: "local", baseUrl: "fixture" }),
}));
const schedule: AutomationSchedule = {
  id: "routine",
  name: "Consulta Diária",
  enabled: false,
  flow: "consulta",
  days_back: 2,
  weekdays: [0, 1, 2, 3, 4, 5, 6],
  time: "08:00",
  revision: 1,
  activated_at: "2026-11-14T10:00:00Z",
  next_run_at: null,
  last_run: null,
  operator_name: "Operador",
};
const run: RunStatus = {
  id: null,
  state: "aguardando",
  flow: null,
  etapaAtual: null,
  cteAtual: null,
  processados: 0,
  total: 0,
  iniciadoEm: null,
  stages: [],
};
const clients: QueryClient[] = [];
beforeEach(() => {
  vi.clearAllMocks();
  fixture.api.getSchedules.mockResolvedValue({
    schedules: [schedule],
    device: "TEST",
    local_time: "2026-11-14T10:00:00Z",
    running: true,
  });
  fixture.api.getRun.mockResolvedValue(run);
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
});
afterEach(() => {
  cleanup();
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
});
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  render(
    <QueryClientProvider client={client}>
      <Schedules />
    </QueryClientProvider>,
  );
  return client;
}

it("inicia a rotina salva mesmo desativada e impede outro clique enquanto aguarda a resposta", async () => {
  let complete: (value: RunStatus) => void = () => {};
  fixture.api.runSchedule.mockImplementation(
    () =>
      new Promise<RunStatus>((resolve) => {
        complete = resolve;
      }),
  );
  const client = mount();
  const button = await screen.findByRole("button", { name: "Iniciar rotina Consulta Diária" });
  expect(button).toBeEnabled();
  fireEvent.click(button);
  await waitFor(() => expect(button).toBeDisabled());
  fireEvent.click(button);
  expect(fixture.api.runSchedule).toHaveBeenCalledExactlyOnceWith("routine");
  const started: RunStatus = { ...run, id: "manual-run", state: "executando", flow: "consulta" };
  await act(async () => {
    complete(started);
  });
  expect(client.getQueryData(["run", "local", "fixture"])).toEqual(started);
  expect(button).toBeDisabled();
});

it("aguarda o encerramento de uma execução em andamento", async () => {
  fixture.api.getRun.mockResolvedValue({ ...run, state: "executando" });
  mount();
  expect(
    await screen.findByRole("button", { name: "Iniciar rotina Consulta Diária" }),
  ).toBeDisabled();
  expect(fixture.api.runSchedule).not.toHaveBeenCalled();
});

it("duplica em um rascunho pausado e salva apenas depois da revisão", async () => {
  fixture.api.getSchedules.mockResolvedValue({
    schedules: [
      { ...schedule, enabled: true, runs_per_day: 3, interval_minutes: 120, max_retries: 2 },
    ],
    device: "TEST",
    running: true,
  });
  fixture.api.createSchedule.mockResolvedValue({ ...schedule, id: "copy" });
  mount();
  fireEvent.keyDown(await screen.findByRole("button", { name: "Mais ações de Consulta Diária" }), {
    key: "Enter",
    code: "Enter",
  });
  fireEvent.click(await screen.findByRole("menuitem", { name: "Duplicar" }));
  expect(screen.getByLabelText("Nome do agendamento")).toHaveValue("Consulta Diária (cópia)");
  expect(fixture.api.createSchedule).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Salvar" }));
  await waitFor(() =>
    expect(fixture.api.createSchedule).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "Consulta Diária (cópia)",
        enabled: false,
        runs_per_day: 3,
        interval_minutes: 120,
        max_retries: 2,
      }),
    ),
  );
});

it("abre o histórico em um painel lateral pelo menu de ações", async () => {
  fixture.api.getScheduleHistory.mockResolvedValue({
    rows: [
      {
        local_date: "2026-11-15",
        slot: 0,
        attempt: 0,
        state: "failed",
        due_at: "2026-11-15T08:00:00Z",
        started_at: "2026-11-15T08:00:00Z",
        finished_at: "2026-11-15T08:02:00Z",
        message: "Falha controlada na atualização do catálogo.",
      },
    ],
    total: 1,
    page: 0,
    page_size: 20,
  });
  mount();
  fireEvent.keyDown(await screen.findByRole("button", { name: "Mais ações de Consulta Diária" }), {
    key: "Enter",
    code: "Enter",
  });
  fireEvent.click(await screen.findByRole("menuitem", { name: "Ver histórico de execuções" }));
  expect(await screen.findByText("Falha controlada na atualização do catálogo.")).toBeVisible();
  expect(fixture.api.getScheduleHistory).toHaveBeenCalledWith("routine", 0);
});
