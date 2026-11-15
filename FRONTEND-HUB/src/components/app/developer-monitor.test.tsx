import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DeveloperMonitorPage } from "./developer-monitor";
import { selectOption } from "@/test/select-option";
import type { DeveloperMonitor, MonitoredDevice, MonitoredSession } from "@/services";

const fixtures = vi.hoisted(() => ({
  api: { getDeveloperConfig: vi.fn(), getDeveloperMonitor: vi.fn() },
}));
vi.mock("@/services", () => ({
  useApi: () => ({ api: fixtures.api, mode: "local", baseUrl: "test" }),
}));

const device: MonitoredDevice = {
  id: "device-01",
  machine_id: "test-pc",
  computer_name: "TEST-PC",
  windows_user: "DOMAIN\\maria",
  mac_addresses: ["00:11:22:33:44:55"],
  version: "0.1.35-r2",
  installation_kind: "installed",
  install_root: "C:\\Cargo Hub",
  first_seen_at: "2026-11-12T10:00:00Z",
  last_seen_at: "2026-11-13T18:00:00Z",
  backend_started_at: "2026-11-13T11:00:00Z",
  backend_status: "online",
  automation_status: "running",
  run_id: "run-01",
  online: true,
  operators: ["Maria"],
};
const session: MonitoredSession = {
  id: "public-session-id",
  machine_id: device.machine_id,
  operator_name: "Maria",
  windows_user: device.windows_user,
  computer_name: device.computer_name,
  mac_addresses: device.mac_addresses,
  login_at: "2026-11-13T11:00:00Z",
  last_seen_at: device.last_seen_at,
  logout_at: null,
  status: "active",
  display_status: "active",
  automation_status: "running",
  run_id: "run-01",
  online: true,
};
const data: DeveloperMonitor = {
  checked_at: device.last_seen_at,
  online_timeout_seconds: 90,
  source: "shared_session_audit",
  truncated: false,
  local_pending_sync: 0,
  summary: {
    detected_installations: 2,
    online_devices: 1,
    logged_in_users: 1,
    running_automations: 1,
    broken_automations: 0,
  },
  devices: [
    device,
    {
      ...device,
      id: "device-02",
      machine_id: "offline-pc",
      computer_name: "OFFLINE-PC",
      windows_user: "DOMAIN\\joao",
      online: false,
      operators: [],
      automation_status: "broken",
    },
  ],
  sessions: [
    session,
    {
      ...session,
      id: "offline-session",
      machine_id: "offline-pc",
      operator_name: "João",
      computer_name: "OFFLINE-PC",
      windows_user: "DOMAIN\\joao",
      online: false,
      display_status: "stale",
      automation_status: "broken",
    },
  ],
};

beforeEach(() => {
  fixtures.api.getDeveloperConfig.mockResolvedValue({ enabled: true });
  fixtures.api.getDeveloperMonitor.mockResolvedValue(data);
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
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});
function show() {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <DeveloperMonitorPage />
    </QueryClientProvider>,
  );
}

describe("console do desenvolvedor", () => {
  it("filtra setor e filial de computadores anteriores e mostra a identificação no painel lateral", async () => {
    fixtures.api.getDeveloperMonitor.mockResolvedValue({
      ...data,
      devices: [
        { ...device, computer_name: "NB-TI-VIN-07" },
        { ...device, id: "purchase", computer_name: "WKS-COMP-RJ02", machine_id: "purchase" },
      ],
    });
    show();
    expect(await screen.findByText("NB-TI-VIN-07")).toBeVisible();
    expect(screen.getByText("WKS-COMP-RJ02")).toBeVisible();
    await selectOption("Filtrar setor", "Compras");
    expect(screen.queryByText("NB-TI-VIN-07")).toBeNull();
    await selectOption("Filtrar filial", "Viana");
    expect(screen.queryByText("WKS-COMP-RJ02")).toBeNull();
    await selectOption("Filtrar filial", "Rio de Janeiro");
    fireEvent.click(screen.getByRole("button", { name: "Detalhes de WKS-COMP-RJ02" }));
    const details = within(screen.getByRole("dialog"));
    expect(details.getByText("Compras")).toBeVisible();
    expect(details.getByText("Rio de Janeiro")).toBeVisible();
    expect(details.getByText("Workstation")).toBeVisible();
  });
  it("busca pelo nome do setor sem depender de acentuação", async () => {
    fixtures.api.getDeveloperMonitor.mockResolvedValue({
      ...data,
      devices: [
        { ...device, computer_name: "NB-MAN-VIN-01" },
        { ...device, id: "other", computer_name: "NB-TI-VIN-07" },
      ],
    });
    show();
    await screen.findByText("NB-MAN-VIN-01");
    fireEvent.change(screen.getByLabelText("Buscar usuários e dispositivos"), {
      target: { value: "manutencao" },
    });
    expect(screen.getByText("NB-MAN-VIN-01")).toBeVisible();
    expect(screen.queryByText("NB-TI-VIN-07")).toBeNull();
  });
  it("restringe a consulta dos usuários quando o modo desenvolvedor está desativado", async () => {
    fixtures.api.getDeveloperConfig.mockResolvedValue({ enabled: false });
    show();
    expect(
      await screen.findByText("Este painel requer o modo desenvolvedor ativo neste computador."),
    ).toBeVisible();
    expect(fixtures.api.getDeveloperMonitor).not.toHaveBeenCalled();
    expect(screen.queryByText("Maria")).toBeNull();
  });
  it("permite buscar por operador e filtrar os computadores por conexão", async () => {
    show();
    expect(await screen.findByText("TEST-PC", { exact: true })).toBeVisible();
    expect(screen.getByText("OFFLINE-PC", { exact: true })).toBeVisible();
    fireEvent.change(screen.getByLabelText("Buscar usuários e dispositivos"), {
      target: { value: "Maria" },
    });
    expect(screen.queryByText("OFFLINE-PC", { exact: true })).toBeNull();
    fireEvent.change(screen.getByLabelText("Buscar usuários e dispositivos"), {
      target: { value: "" },
    });
    await selectOption("Filtrar conexão", "Offline / sem sinal");
    expect(screen.queryByText("TEST-PC", { exact: true })).toBeNull();
    expect(screen.getByText("Último estado recebido")).toBeVisible();
  });
  it("abre os detalhes de versão, identificação e pasta sem confundir offline com desinstalado", async () => {
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Detalhes de TEST-PC" }));
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent("C:\\Cargo Hub");
    expect(dialog).toHaveTextContent("00:11:22:33:44:55");
    expect(dialog).toHaveTextContent("0.1.35-r2");
    expect(screen.queryByText("Console do desenvolvedor")).not.toBeInTheDocument();
  });
  it("informa indisponibilidade do registro compartilhado sem inventar usuários", async () => {
    fixtures.api.getDeveloperMonitor.mockRejectedValue(
      new Error("Registro compartilhado indisponível."),
    );
    show();
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Registro compartilhado indisponível."),
    );
    expect(screen.queryByText("Maria")).toBeNull();
  });
});
