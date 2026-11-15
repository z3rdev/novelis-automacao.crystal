import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ActivityLog } from "./activity-log";
import type { LogEntry } from "@/services";

const state = vi.hoisted(() => ({ rows: [] as LogEntry[] }));
vi.mock("@/services", () => ({
  useApi: () => ({
    mode: "local",
    baseUrl: "fixture",
    api: { listLogs: async () => structuredClone(state.rows) },
  }),
}));
const entry = (id: string, patch: Partial<LogEntry> = {}): LogEntry => ({
  id,
  time: "2026-11-14T12:00:00Z",
  severity: "info",
  source: "xml_sefaz.saved",
  message: "XML salvo em C:\\documentos\\arquivo.xml.",
  details: JSON.stringify({ cte: "2-10-10", file: "C:\\documentos\\arquivo.xml" }),
  ...patch,
});
beforeEach(() => {
  state.rows = [
    entry("1"),
    entry("2", {
      severity: "erro",
      source: "crystal_pdf.error",
      message: "Falha ao gerar PDF: código diferente.",
      details: JSON.stringify({
        cte: "2-10-11",
        password: "fixture-private",
        nested: { token: "fixture-token" },
      }),
    }),
    entry("3", { severity: "debug", source: "trace", message: "Rastreamento técnico" }),
  ];
});
afterEach(cleanup);
function mount(callback = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ActivityLog onLatestXml={callback} />
    </QueryClientProvider>,
  );
  return client;
}
it("mostra mensagens legíveis, busca os eventos e mantém os detalhes técnicos no painel lateral", async () => {
  const client = mount();
  await screen.findByText("XML salvo.");
  expect(screen.queryByText("Rastreamento técnico")).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Buscar eventos"), {
    target: { value: "código diferente" },
  });
  expect(screen.queryByText("XML salvo.")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Ver evento: Falha ao gerar PDF/ }));
  expect(screen.getByRole("dialog")).toHaveTextContent("crystal_pdf.error");
  expect(screen.getByRole("dialog")).toHaveTextContent("[oculto]");
  expect(screen.getByRole("dialog")).not.toHaveTextContent("fixture-private");
  expect(screen.getByRole("dialog")).not.toHaveTextContent("fixture-token");
  client.clear();
});
it("pausa a visualização sem perder os eventos que chegam nem interromper o estado da SEFAZ", async () => {
  const latest = vi.fn(),
    client = mount(latest);
  await screen.findByText("XML salvo.");
  fireEvent.click(screen.getByRole("button", { name: "Pausar" }));
  state.rows.push(
    entry("4", { source: "xml_sefaz.captcha", message: "Aguardando confirmação na SEFAZ." }),
  );
  await act(async () => {
    await client.invalidateQueries({ queryKey: ["logs"] });
  });
  await waitFor(() =>
    expect(latest).toHaveBeenLastCalledWith(expect.objectContaining({ id: "4" })),
  );
  expect(screen.queryByText("Aguardando confirmação na SEFAZ.")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Retomar" }));
  await screen.findByText("Aguardando confirmação na SEFAZ.");
  client.clear();
});

it("ordena por horário decrescente e desempata pelo ID sem alterar os dados da consulta", async () => {
  state.rows = [
    entry("8", { source: "fixture", time: "2026-11-14T09:00:00Z", message: "Mais antigo" }),
    entry("2", { source: "fixture", time: "2026-11-15T09:00:00Z", message: "Mais recente" }),
    entry("9", { source: "fixture", time: "2026-11-14T09:00:00Z", message: "Desempate recente" }),
  ];
  const client = mount();
  await screen.findByText("Mais recente");
  expect(
    screen
      .getAllByRole("button", { name: /^Ver evento:/ })
      .map((row) => row.getAttribute("data-log-id")),
  ).toEqual(["2", "9", "8"]);
  expect(
    client.getQueryData<LogEntry[]>(["logs", "local", "fixture"])?.map((row) => row.id),
  ).toEqual(["8", "2", "9"]);
  fireEvent.click(screen.getByRole("button", { name: "Limpar visualização" }));
  expect(screen.queryByText("Mais antigo")).not.toBeInTheDocument();
  expect(screen.queryByText("Mais recente")).not.toBeInTheDocument();
  state.rows.unshift(entry("10", { source: "fixture", message: "Chegou agora" }));
  await act(async () => {
    await client.invalidateQueries({ queryKey: ["logs"] });
  });
  await screen.findByText("Chegou agora");
  expect(screen.getAllByRole("button", { name: /^Ver evento:/ })).toHaveLength(1);
  client.clear();
});

it("segue os eventos pelo topo e permite voltar aos recentes depois de rolar", async () => {
  const client = mount();
  const message = await screen.findByText("XML salvo.");
  const viewport = message.closest("[data-log-id]")!.parentElement!.parentElement!;
  viewport.scrollTop = 160;
  fireEvent.scroll(viewport);
  fireEvent.click(screen.getByRole("button", { name: "Ir para recentes" }));
  expect(viewport.scrollTop).toBe(0);
  expect(screen.queryByRole("button", { name: "Ir para recentes" })).not.toBeInTheDocument();
  client.clear();
});
