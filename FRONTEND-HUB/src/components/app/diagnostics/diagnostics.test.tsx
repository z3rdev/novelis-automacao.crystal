import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DiagnosticRequest } from "@/services/remote-diagnostics";
import { DiagnosticCenter } from "./diagnostic-center";
import { DiagnosticEvents } from "./diagnostic-events";
import { DiagnosticReportPanel } from "./diagnostic-report";
import { selectOption } from "@/test/select-option";

const fixture = vi.hoisted(() => ({
  api: {
    getDeveloperConfig: vi.fn(),
    getDeveloperMonitor: vi.fn(),
    getDiagnosticAgents: vi.fn(),
    listDiagnosticRequests: vi.fn(),
    requestDiagnostic: vi.fn(),
    getDiagnosticRequest: vi.fn(),
  },
  saveFile: vi.fn(),
  openPath: vi.fn(),
}));
vi.mock("@/services", () => ({
  useApi: () => ({ api: fixture.api, mode: "local", baseUrl: "test" }),
}));
vi.mock("@/services/desktop", () => ({
  desktop: { saveFile: fixture.saveFile, openPath: fixture.openPath },
}));

const value: DiagnosticRequest = {
  id: "request-1",
  device_id: "pc-1",
  computer_name: "TEST-PC",
  requested_by: "DOMAIN\\dev",
  requested_at: "2026-11-15T13:00:00Z",
  expires_at: "2026-11-15T13:10:00Z",
  state: "completed",
  started_at: null,
  finished_at: null,
  error_code: "",
  options: { max_runs: 5, days_back: 1 },
  result: {
    schema_version: 1,
    checked_at: "2026-11-15T13:00:00Z",
    complete: false,
    device: { computer_name: "TEST-PC", windows_user: "DOMAIN\\op", version: "test" },
    scope: { max_runs: 5, days_back: 1 },
    duration_seconds: 10,
    limitations: [],
    summary: {
      runs: 1,
      failed_runs: 1,
      cancelled_runs: 0,
      confirmed_tickets: 0,
      http_events: 1,
      issues: 1,
    },
    runs: [],
    http: [],
    checks: [
      {
        id: "sql",
        title: "Conexão SQL",
        status: "failed",
        message: "Falha na consulta",
        source: "live",
        checked_at: "2026-11-15T13:00:00Z",
        details: {},
      },
    ],
  },
};

beforeEach(() => {
  fixture.api.getDeveloperConfig.mockResolvedValue({ enabled: true });
  fixture.api.getDeveloperMonitor.mockResolvedValue({
    devices: [
      { id: "pc-1", computer_name: "TEST-PC", installation_kind: "installed" },
      { id: "legacy", computer_name: "LEGACY-PC", installation_kind: "installed" },
    ],
  });
  fixture.api.getDiagnosticAgents.mockResolvedValue({
    agents: [
      {
        device_id: "pc-1",
        computer_name: "TEST-PC",
        online: true,
        protocol: 1,
        installation_kind: "installed",
      },
    ],
  });
  fixture.api.listDiagnosticRequests.mockResolvedValue({ requests: [] });
  fixture.api.requestDiagnostic.mockResolvedValue({ ...value, state: "queued", result: null });
  fixture.api.getDiagnosticRequest.mockResolvedValue({ ...value, state: "queued", result: null });
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
function show() {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <DiagnosticCenter />
    </QueryClientProvider>,
  );
}

describe("central de diagnóstico", () => {
  it("orienta a reiniciar a prévia quando o serviço ainda não possui a central", async () => {
    fixture.api.getDiagnosticAgents.mockRejectedValue(new Error("Not Found"));
    show();
    await screen.findByText(
      "Reinicie a prévia para carregar a Central de diagnóstico no serviço local.",
    );
    expect(screen.getByRole("button", { name: "Solicitar diagnóstico" })).toBeDisabled();
  });

  it("não consulta a fila quando o modo desenvolvedor está desativado", async () => {
    fixture.api.getDeveloperConfig.mockResolvedValue({ enabled: false });
    show();
    await screen.findByText("Acesso exclusivo do desenvolvedor neste computador.");
    expect(fixture.api.getDiagnosticAgents).not.toHaveBeenCalled();
    expect(fixture.api.listDiagnosticRequests).not.toHaveBeenCalled();
  });

  it("identifica clientes antigos e solicita somente as opções selecionadas", async () => {
    show();
    fireEvent.keyDown(await screen.findByRole("combobox", { name: "Computador do diagnóstico" }), {
      key: "ArrowDown",
    });
    const old = await screen.findByRole("option", { name: /LEGACY-PC/ });
    expect(old).toHaveAttribute("aria-disabled", "true");
    expect(old).toHaveTextContent("Atualizar cliente");
    fireEvent.click(screen.getByRole("option", { name: /TEST-PC/ }));
    await selectOption("Quantidade de execuções", "Últimas 5");
    await selectOption("Período do diagnóstico", "Último dia");
    fireEvent.click(screen.getByRole("button", { name: "Solicitar diagnóstico" }));
    await waitFor(() => expect(fixture.api.requestDiagnostic).toHaveBeenCalledWith("pc-1", 5, 1));
    await screen.findByText("Aguardando o computador atender à solicitação.");
  });

  it("mostra coleta parcial e disponibiliza o relatório sem afirmar sucesso do ambiente", () => {
    const download = vi.fn();
    render(
      <DiagnosticReportPanel
        open
        value={value}
        error={undefined}
        onClose={vi.fn()}
        onDownload={download}
      />,
    );
    expect(screen.getByText("Parcial")).toBeVisible();
    expect(screen.getByText("Falha na consulta")).toBeVisible();
    expect(screen.getByText("Falhou")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Baixar JSON" }));
    expect(download).toHaveBeenCalledWith(value);
  });

  it("HTTP 200 sem confirmação permanece sem confirmação e preserva os dois códigos", () => {
    render(
      <DiagnosticEvents
        http
        events={[
          {
            time: "2026-11-15T13:00:00Z",
            severity: "warn",
            source: "novelis.save",
            message: "Confirmação não obtida",
            details: {
              cte: "1-10-100",
              status: "unconfirmed",
              save_http: 200,
              readback_http: 403,
              attachments_visible: false,
            },
          },
        ]}
      />,
    );
    expect(screen.queryByText("Confirmado")).not.toBeInTheDocument();
    expect(screen.getByText("200")).toBeVisible();
    expect(screen.getByText("403")).toBeVisible();
    expect(screen.getByText("Não")).toBeVisible();
  });
});
