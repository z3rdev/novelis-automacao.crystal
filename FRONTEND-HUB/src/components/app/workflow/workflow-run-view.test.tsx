import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { RunStatus } from "@/services";
import { initialWorkflow } from "@/services/scheduled-workflow";
import { StagesView } from "../stage-progress";
import { RunSummary } from "../run-panel";
import { workflowCatalog } from "./catalog";
import { WorkflowRunView } from "./workflow-run-view";
import type { WorkflowRun } from "@/services/workflow-run";

afterEach(cleanup);

describe("Live custom workflow", () => {
  it("mantém nove etapas em uma sequência única com progresso apenas da etapa ativa", () => {
    const kinds = [
      "novelis_report",
      "sql",
      "compare",
      "pdf",
      "xml",
      "tickets",
      "generate_report",
      "open_report",
      "completion_modal",
    ] as const;
    const workflow: WorkflowRun = {
      name: "Fluxo de abertura",
      completed: 5,
      total: 9,
      current_node_id: "step-5",
      completion: null,
      nodes: kinds.map((kind, index) => ({
        id: `step-${index}`,
        kind,
        label: workflowCatalog[kind].label,
        state: index < 5 ? "concluida" : index === 5 ? "executando" : "aguardando",
        options: { start_days_ago: 0, end_days_ago: 0 },
        done: index < 5 ? 1 : 0,
        total: index <= 5 ? 1 : 0,
        detail: index === 5 ? "Conferindo a confirmação do chamado." : "",
        started_at: null,
        finished_at: null,
      })),
    };
    const { container, rerender } = render(<WorkflowRunView workflow={workflow} />);
    expect(screen.getAllByRole("listitem")).toHaveLength(9);
    expect(screen.getAllByRole("progressbar")).toHaveLength(1);
    expect(container.querySelector('[aria-current="step"]')).toHaveAttribute(
      "data-workflow-node",
      "step-5",
    );
    rerender(
      <WorkflowRunView
        workflow={{
          ...workflow,
          current_node_id: null,
          nodes: workflow.nodes.map((node) => ({ ...node, state: "concluida" })),
        }}
      />,
    );
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    expect(container.querySelector('[aria-current="step"]')).toBeNull();
  });
  it("renders the exact node sequence and its active step in the overview", () => {
    const graph = initialWorkflow(2);
    const run: RunStatus = {
      id: "custom",
      flow: "personalizado",
      state: "executando",
      etapaAtual: "consulta",
      cteAtual: null,
      processados: 0,
      total: 10,
      iniciadoEm: "2026-11-14T12:00:00Z",
      stages: [],
      workflow: {
        name: "Rotina da manhã",
        current_node_id: graph.nodes[1]!.id,
        completed: 1,
        total: 6,
        completion: null,
        nodes: graph.nodes.map((node, index) => ({
          ...node,
          label: workflowCatalog[node.kind].label,
          done: index ? 0 : 3,
          total: 3,
          detail: index === 1 ? "Consultando SQL" : "",
          started_at: null,
          finished_at: null,
          state: index === 0 ? "concluida" : index === 1 ? "executando" : "aguardando",
        })),
      },
    };
    const { container } = render(
      <>
        <RunSummary run={run} />
        <StagesView run={run} />
      </>,
    );
    expect(screen.getByText("Rotina da manhã")).toBeInTheDocument();
    expect(screen.getByText("Etapas concluídas")).toBeInTheDocument();
    expect(screen.getAllByText("Consultar SQL")).toHaveLength(2);
    expect(screen.queryByText("Documentos · PDF e XML simultâneos")).not.toBeInTheDocument();
    expect(
      [...container.querySelectorAll("[data-workflow-node]")].map((card) =>
        card.getAttribute("data-workflow-node"),
      ),
    ).toEqual(graph.nodes.map((node) => node.id));
    expect(screen.getByText("Consultando SQL")).toBeInTheDocument();
  });
});
