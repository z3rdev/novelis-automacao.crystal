import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { RunStatus } from "@/services";
import { OverviewConsultAction } from "./overview-consult-action";
import { RunSummary } from "./run-panel";
import { logCategory } from "./log-presentation";

const mock = vi.hoisted(() => ({ stop: vi.fn() }));
vi.mock("@/services", () => ({
  useApi: () => ({ mode: "local", baseUrl: "fixture", api: { stopRun: mock.stop } }),
}));
const run = (state: RunStatus["state"]): RunStatus => ({
  id: "fixture",
  flow: "completo",
  state,
  etapaAtual: "consulta",
  cteAtual: null,
  processados: 0,
  total: 0,
  iniciadoEm: null,
  stages: [{ id: "consulta", state: "executando", done: 0, total: 0, atividade: "SQL Server" }],
});
beforeEach(() => { mock.stop.mockReset(); });
afterEach(cleanup);

function mount(value = run("aguardando"), invalid = false, refreshing = false) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  client.setQueryData(["run", "local", "fixture"], value);
  const consult = vi.fn();
  render(
    <QueryClientProvider client={client}>
      <OverviewConsultAction
        run={value}
        invalid={invalid}
        refreshing={refreshing}
        onConsult={consult}
      />
    </QueryClientProvider>,
  );
  return { client, consult };
}

it("inicia a consulta somente quando a automação está ociosa", () => {
  const { client, consult } = mount();
  fireEvent.click(screen.getByRole("button", { name: "Consultar agora" }));
  expect(consult).toHaveBeenCalledOnce();
  expect(mock.stop).not.toHaveBeenCalled();
  client.clear();
});

it("troca a consulta por parada real e impede uma segunda parada enquanto encerra", async () => {
  let finish!: (value: RunStatus) => void;
  mock.stop.mockImplementation(
    () =>
      new Promise<RunStatus>((resolve) => {
        finish = resolve;
      }),
  );
  const { client, consult } = mount(run("executando"), true, true);
  fireEvent.click(screen.getByRole("button", { name: "Parar automação" }));
  await waitFor(() => expect(mock.stop).toHaveBeenCalledOnce());
  expect(consult).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: "Parando…" })).toBeDisabled();
  expect(client.getQueryData<RunStatus>(["run", "local", "fixture"])?.state).toBe("parando");
  fireEvent.click(screen.getByRole("button", { name: "Parando…" }));
  expect(mock.stop).toHaveBeenCalledOnce();
  await act(async () => finish(run("cancelada")));
  client.clear();
});

it("mantém Parando desabilitado quando a parada veio de outra tela", () => {
  const { client } = mount(run("parando"));
  expect(screen.getByRole("button", { name: "Parando…" })).toBeDisabled();
  expect(screen.queryByRole("button", { name: "Consultar agora" })).not.toBeInTheDocument();
  client.clear();
});

it("mostra a fonte da consulta na visão geral", () => {
  const value = run("executando");
  render(<RunSummary run={value} />);
  expect(screen.getByText("SQL Server")).toBeInTheDocument();
});

it("distingue SQL, relatório e arquivos nas categorias do monitor", () => {
  expect(logCategory("pendentes.sql_refresh")).toBe("SQL Server");
  expect(logCategory("pendentes.manual_sql_refresh")).toBe("SQL Server");
  expect(logCategory("novelis_relatorio.http_download")).toBe("Relatório Novelis");
  expect(logCategory("pendentes.novelis_relatorio_final")).toBe("Relatório Novelis");
  expect(logCategory("pendentes.files_check")).toBe("Arquivos");
  expect(logCategory("pendentes.pdf_xml_parallel")).toBe("Execução");
});
