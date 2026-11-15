import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { RunStatus } from "@/services";
import { AppDialogs } from "../app-dialogs";
import { WorkflowCompletionMonitor } from "./workflow-completion";

const fixture = vi.hoisted(() => ({ run: null as RunStatus | null, navigate: vi.fn() }));
vi.mock("@/services", () => ({ useApi: () => ({ mode: "local", baseUrl: "fixture" }) }));
vi.mock("@tanstack/react-router", () => ({ useNavigate: () => fixture.navigate }));
vi.mock("../run-panel", () => ({ useRun: () => ({ data: fixture.run }) }));

function result(openReport = false, showModal = true): RunStatus {
  return {
    id: "finished-flow",
    flow: "personalizado",
    state: "concluida",
    etapaAtual: null,
    cteAtual: null,
    processados: 0,
    total: 0,
    iniciadoEm: null,
    finalizadoEm: "2026-11-14T23:00:00Z",
    stages: [],
    workflow: {
      name: "Rotina noturna",
      current_node_id: null,
      completed: 3,
      total: 3,
      nodes: [],
      completion: {
        ready: true,
        show_modal: showModal,
        open_report: openReport,
        report_id: "daily-id",
        report_date: "2026-11-14",
        opened_count: 5,
        existing_count: 1,
        error: null,
      },
    },
  };
}

beforeEach(() => {
  localStorage.clear();
  fixture.navigate.mockReset();
  fixture.run = result();
});
afterEach(cleanup);

describe("Workflow completion actions", () => {
  it("shows the result once even when the run is polled again", async () => {
    const view = render(
      <AppDialogs>
        <WorkflowCompletionMonitor />
      </AppDialogs>,
    );
    expect(await screen.findByRole("heading", { name: "Fluxo concluído" })).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Fechar" }));
    fixture.run = result();
    view.rerender(
      <AppDialogs>
        <WorkflowCompletionMonitor />
      </AppDialogs>,
    );
    expect(screen.queryByRole("heading", { name: "Fluxo concluído" })).not.toBeInTheDocument();
    expect(fixture.navigate).not.toHaveBeenCalled();
  });

  it("opens the report directly when only that action is selected", async () => {
    fixture.run = result(true, false);
    render(
      <AppDialogs>
        <WorkflowCompletionMonitor />
      </AppDialogs>,
    );
    await waitFor(() =>
      expect(fixture.navigate).toHaveBeenCalledWith({
        to: "/relatorios",
        search: { report: "daily-id" },
      }),
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("opens the report after the completion modal is dismissed when both are selected", async () => {
    fixture.run = result(true, true);
    render(
      <AppDialogs>
        <WorkflowCompletionMonitor />
      </AppDialogs>,
    );
    expect(await screen.findByRole("heading", { name: "Fluxo concluído" })).toBeInTheDocument();
    expect(fixture.navigate).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Fechar" }));
    expect(fixture.navigate).toHaveBeenCalledWith({
      to: "/relatorios",
      search: { report: "daily-id" },
    });
  });

  it("waits for report generation before displaying completion", () => {
    fixture.run!.workflow!.completion!.ready = false;
    render(
      <AppDialogs>
        <WorkflowCompletionMonitor />
      </AppDialogs>,
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(fixture.navigate).not.toHaveBeenCalled();
  });
});
