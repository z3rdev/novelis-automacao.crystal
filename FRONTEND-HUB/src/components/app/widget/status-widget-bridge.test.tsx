import { act, cleanup, render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
import { widgetSnapshotKey } from "@/services/status-widget";
import { StatusWidgetBridge } from "./status-widget-bridge";

const fixture = vi.hoisted(() => ({
  api: { getSession: vi.fn(), getRun: vi.fn(), getSchedules: vi.fn() },
  navigate: vi.fn(),
  listener: vi.fn().mockResolvedValue(() => {}),
}));
vi.mock("@/services", () => ({
  useApi: () => ({ api: fixture.api, mode: "local", baseUrl: "fixture" }),
}));
vi.mock("@/services/desktop", () => ({
  desktop: { isDesktop: true, onWidgetNavigate: fixture.listener },
}));
vi.mock("@tanstack/react-router", () => ({ useNavigate: () => fixture.navigate }));

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.clearAllMocks();
  localStorage.clear();
  Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
});

it("atualiza o estado compartilhado enquanto a janela principal está oculta", async () => {
  vi.useFakeTimers();
  Object.defineProperty(document, "visibilityState", { configurable: true, value: "hidden" });
  fixture.api.getSession.mockResolvedValue({ session: { id: "operator-fixture" } });
  const run = {
    id: "r1",
    flow: "completo",
    state: "executando",
    etapaAtual: "pdf",
    cteAtual: "1-10-123",
    processados: 1,
    total: 3,
    iniciadoEm: null,
    stages: [],
  };
  fixture.api.getRun.mockResolvedValue(run);
  fixture.api.getSchedules.mockResolvedValue({
    schedules: [],
    device: "TEST-PC",
    local_time: "",
    running: true,
  });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  });
  render(
    <QueryClientProvider client={client}>
      <StatusWidgetBridge />
    </QueryClientProvider>,
  );
  await act(async () => {
    await vi.advanceTimersByTimeAsync(100);
  });
  expect(JSON.parse(localStorage.getItem(widgetSnapshotKey)!)).toMatchObject({
    connection: "connected",
    activity: "Gerando PDF",
    cte: "1-10-123",
  });
  fixture.api.getRun.mockResolvedValue({ ...run, etapaAtual: "xml" });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(3_100);
  });
  expect(fixture.api.getRun.mock.calls.length).toBeGreaterThan(1);
  expect(JSON.parse(localStorage.getItem(widgetSnapshotKey)!)).toMatchObject({
    connection: "connected",
    activity: "Baixando XML",
  });
  client.clear();
});

it("publica a necessidade de login quando a sessão está ausente", async () => {
  vi.useFakeTimers();
  fixture.api.getSession.mockResolvedValue({ session: null });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  });
  render(
    <QueryClientProvider client={client}>
      <StatusWidgetBridge />
    </QueryClientProvider>,
  );
  await act(async () => {
    await vi.advanceTimersByTimeAsync(100);
  });
  expect(JSON.parse(localStorage.getItem(widgetSnapshotKey)!)).toMatchObject({
    connection: "login_required",
  });
  expect(fixture.api.getSchedules).not.toHaveBeenCalled();
  client.clear();
});
