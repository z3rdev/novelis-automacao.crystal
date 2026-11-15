import { useState } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactFlowProps } from "@xyflow/react";
import type { CargoNode } from "./workflow-node";
import { WorkflowEditor } from "./workflow-editor";
import { ScheduleForm } from "../schedule-form";
import { emptySchedule } from "@/services/schedule-options";

vi.mock("@xyflow/react", async (original) => {
  const actual = await original<typeof import("@xyflow/react")>();
  return {
    ...actual,
    Background: () => null,
    Controls: () => null,
    ReactFlow: ({ nodes = [], onNodeClick }: ReactFlowProps<CargoNode>) => (
      <div>
        {nodes.map((node) => (
          <button type="button" key={node.id} onClick={(event) => onNodeClick?.(event, node)}>
            Etapa {node.data.kind}
          </button>
        ))}
      </div>
    ),
  };
});

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

describe("Visual schedule editor", () => {
  it("adiciona e salva a etapa Atualizar tarifário", () => {
    const save = vi.fn();
    render(<WorkflowEditor days={0} onClose={vi.fn()} onSave={save} />);
    fireEvent.click(screen.getByRole("button", { name: /Atualizar tarifário/ }));
    expect(
      screen.getByText("Atualiza o catálogo pelo portal e aguarda a conclusão."),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Usar no agendamento" }));
    const graph = save.mock.calls[0]![0];
    expect(graph.nodes.at(-1).kind).toBe("tariffs");
    expect(graph.edges.at(-1).target).toBe(graph.nodes.at(-1).id);
  });
  it("persists query periods and the six-node connected sequence", () => {
    const save = vi.fn();
    render(<WorkflowEditor days={0} onClose={vi.fn()} onSave={save} />);
    fireEvent.click(screen.getByRole("button", { name: "Etapa sql" }));
    fireEvent.change(screen.getByLabelText("De quantos dias atrás"), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText("Até quantos dias atrás"), { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: "Usar no agendamento" }));
    const graph = save.mock.calls[0]![0];
    expect(graph.nodes).toHaveLength(6);
    expect(graph.edges).toHaveLength(5);
    expect(graph.nodes.find((node: CargoNode["data"]) => node.kind === "sql").options).toEqual({
      start_days_ago: 2,
      end_days_ago: 1,
    });
  });

  it("reconnects the sequence when a selected document step is removed", () => {
    const save = vi.fn();
    render(<WorkflowEditor days={0} onClose={vi.fn()} onSave={save} />);
    fireEvent.click(screen.getByRole("button", { name: "Etapa pdf" }));
    fireEvent.click(screen.getByRole("button", { name: "Excluir etapa" }));
    fireEvent.click(screen.getByRole("button", { name: "Usar no agendamento" }));
    expect(save.mock.calls[0]![0].nodes).toHaveLength(5);
    expect(save.mock.calls[0]![0].edges).toHaveLength(4);
  });

  it("keeps invalid query periods from being applied", () => {
    render(<WorkflowEditor days={0} onClose={vi.fn()} onSave={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Etapa sql" }));
    fireEvent.change(screen.getByLabelText("Até quantos dias atrás"), { target: { value: "2" } });
    expect(screen.getByRole("alert")).toHaveTextContent("período");
    expect(screen.getByRole("button", { name: "Usar no agendamento" })).toBeDisabled();
  });

  it("attaches the created flow to the schedule draft before saving", () => {
    const save = vi.fn();
    function Form() {
      const [value, onChange] = useState({ ...emptySchedule(), name: "Manhã" });
      return (
        <ScheduleForm
          value={value}
          onChange={onChange}
          saving={false}
          editing={false}
          onSave={() => save(value)}
          onCancel={vi.fn()}
        />
      );
    }
    render(<Form />);
    fireEvent.click(screen.getByRole("radio", { name: /Fluxo personalizado/ }));
    fireEvent.click(screen.getByRole("button", { name: "Criar fluxo personalizado" }));
    fireEvent.click(screen.getByRole("button", { name: "Usar no agendamento" }));
    expect(save).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Salvar" }));
    expect(save.mock.calls[0]![0].flow).toBe("personalizado");
    expect(save.mock.calls[0]![0].workflow.nodes).toHaveLength(6);
  });
});
