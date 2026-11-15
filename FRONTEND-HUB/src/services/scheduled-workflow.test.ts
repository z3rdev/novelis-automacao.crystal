import { describe, expect, it } from "vitest";
import {
  initialWorkflow,
  workflowError,
  workflowOrder,
  type ScheduledWorkflow,
  type WorkflowNode,
} from "./scheduled-workflow";

describe("Scheduled workflow validation", () => {
  it("permite atualizar o tarifário sem depender de consulta SQL", () => {
    const seed = initialWorkflow();
    const tariffs: WorkflowNode = { ...seed.nodes[0]!, id: "tariffs", kind: "tariffs" };
    const standalone = { ...seed, nodes: [tariffs], edges: [] };
    expect(workflowError(standalone)).toBeNull();
    const first = seed.nodes[0]!;
    seed.nodes.unshift(tariffs);
    seed.edges.unshift({ source: tariffs.id, target: first.id });
    expect(workflowError(seed)).toBeNull();
    expect(workflowOrder(seed).nodes[0]!.kind).toBe("tariffs");
  });
  it("validates report and modal actions at the end of the sequence", () => {
    const flow = initialWorkflow();
    const previous = flow.nodes.at(-1)!;
    const generate: WorkflowNode = { ...previous, id: "generate", kind: "generate_report" };
    const open = { ...previous, id: "open", kind: "open_report" as const };
    const modal = { ...previous, id: "modal", kind: "completion_modal" as const };
    flow.nodes.push(generate, open, modal);
    flow.edges.push(
      { source: previous.id, target: generate.id },
      { source: generate.id, target: open.id },
      { source: open.id, target: modal.id },
    );
    expect(workflowError(flow)).toBeNull();
    generate.kind = "open_report";
    expect(workflowError(flow)).toContain("Gerar relatório");
  });
  it("follows connections independently of card positions and array order", () => {
    const flow = initialWorkflow(2);
    flow.nodes.reverse();
    expect(workflowOrder(flow).nodes.map((node) => node.kind)).toEqual([
      "novelis_report",
      "sql",
      "compare",
      "pdf",
      "xml",
      "tickets",
    ]);
    expect(workflowError(flow)).toBeNull();
  });

  it("rejects disconnected nodes and cycles", () => {
    const flow = initialWorkflow();
    flow.edges.pop();
    expect(workflowError(flow)).toContain("conecte");
    const cycle = initialWorkflow();
    cycle.edges.push({ source: cycle.nodes.at(-1)!.id, target: cycle.nodes[0]!.id });
    expect(workflowError(cycle)).toContain("início");
  });

  it("requires fresh SQL and Novelis comparison before opening tickets", () => {
    const flow = initialWorkflow();
    const compare = flow.nodes.find((node) => node.kind === "compare")!;
    compare.kind = "sql";
    expect(workflowError(flow)).toContain("Compare");
  });

  it("supports standalone SQL and PDF with bounded periods", () => {
    const flow = initialWorkflow(2);
    flow.nodes = flow.nodes.filter((node) => node.kind === "sql" || node.kind === "pdf");
    flow.edges = [{ source: flow.nodes[0]!.id, target: flow.nodes[1]!.id }];
    expect(workflowError(flow)).toBeNull();
    flow.nodes[0]!.options.end_days_ago = 3;
    expect(workflowError(flow)).toContain("período");
  });

  it("rejects branching connections", () => {
    const flow: ScheduledWorkflow = initialWorkflow();
    flow.edges.push({ source: flow.nodes[0]!.id, target: flow.nodes.at(-1)!.id });
    expect(workflowError(flow)).toContain("única sequência");
  });
});
