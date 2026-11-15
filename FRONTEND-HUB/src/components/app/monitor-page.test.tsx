import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { LogEntry, RunStatus } from "@/services";
import { Monitor } from "@/routes/monitor";

const fixture = vi.hoisted(() => ({
  api: {
    getRun: vi.fn(),
    listLogs: vi.fn(),
    getBrowserFrame: vi.fn(),
    focusBrowser: vi.fn(),
    stopRun: vi.fn(),
  },
}));
vi.mock("@/services", () => ({
  useApi: () => ({ api: fixture.api, mode: "local", baseUrl: "fixture" }),
}));
const run: RunStatus = {
  id: "run-fixture",
  flow: "somente_xml",
  state: "executando",
  etapaAtual: "xml",
  cteAtual: "8-10-1559",
  processados: 0,
  total: 1,
  iniciadoEm: "2026-11-14T12:00:00Z",
  stages: [{ id: "xml", state: "executando", done: 0, total: 1 }],
};
const clients: QueryClient[] = [];
beforeEach(() => {
  vi.clearAllMocks();
  fixture.api.getRun.mockResolvedValue(run);
  fixture.api.listLogs.mockResolvedValue([]);
  fixture.api.focusBrowser.mockResolvedValue({});
  fixture.api.stopRun.mockResolvedValue({ ...run, state: "cancelada" });
});
afterEach(() => {
  cleanup();
  clients.splice(0).forEach((client) => client.clear());
});
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  render(
    <QueryClientProvider client={client}>
      <Monitor />
    </QueryClientProvider>,
  );
}

it("mostra a execução e os eventos sem carregar capturas do navegador", async () => {
  mount();
  expect(await screen.findByText("8-10-1559")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Atividade da automação" })).toBeInTheDocument();
  expect(screen.queryByText("Navegador da automação")).not.toBeInTheDocument();
  expect(fixture.api.getBrowserFrame).not.toHaveBeenCalled();
});

it("mantém o acesso ao navegador SEFAZ somente quando há confirmação pendente", async () => {
  const event: LogEntry = {
    id: "1",
    time: "2026-11-14T12:01:00Z",
    severity: "info",
    source: "xml_sefaz.captcha",
    message: "Aguardando confirmação.",
  };
  fixture.api.listLogs.mockResolvedValue([event]);
  mount();
  fireEvent.click(await screen.findByRole("button", { name: "Mostrar navegador SEFAZ" }));
  await waitFor(() => expect(fixture.api.focusBrowser).toHaveBeenCalledTimes(1));
  expect(fixture.api.getBrowserFrame).not.toHaveBeenCalled();
});

it("reutiliza a interrupção do fluxo no monitor", async () => {
  mount();
  fireEvent.click(await screen.findByRole("button", { name: "Parar automação" }));
  await waitFor(() => expect(fixture.api.stopRun).toHaveBeenCalledTimes(1));
});
