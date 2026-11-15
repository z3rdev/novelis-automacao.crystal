export type WorkflowKind =
  | "tariffs"
  | "novelis_report"
  | "sql"
  | "compare"
  | "files"
  | "pdf"
  | "xml"
  | "proof"
  | "tickets"
  | "generate_report"
  | "open_report"
  | "completion_modal";
export interface WorkflowOptions {
  start_days_ago: number;
  end_days_ago: number;
}
export interface WorkflowNode {
  id: string;
  kind: WorkflowKind;
  position: { x: number; y: number };
  options: WorkflowOptions;
}
export interface ScheduledWorkflow {
  version: 1;
  name: string;
  nodes: WorkflowNode[];
  edges: { source: string; target: string }[];
}

export function workflowOrder(flow: ScheduledWorkflow) {
  const nodes = new Map(flow.nodes.map((node) => [node.id, node]));
  if (!nodes.size) return { nodes: [], error: "Adicione uma etapa ao fluxo." };
  if (nodes.size !== flow.nodes.length)
    return { nodes: [], error: "Os identificadores das etapas devem ser únicos." };
  const incoming = new Map<string, string>();
  const outgoing = new Map<string, string>();
  for (const edge of flow.edges) {
    if (!nodes.has(edge.source) || !nodes.has(edge.target))
      return { nodes: [], error: "Uma conexão aponta para uma etapa inexistente." };
    if (outgoing.has(edge.source) || incoming.has(edge.target))
      return { nodes: [], error: "Conecte as etapas em uma única sequência." };
    outgoing.set(edge.source, edge.target);
    incoming.set(edge.target, edge.source);
  }
  const starts = flow.nodes.filter((node) => !incoming.has(node.id));
  if (starts.length !== 1)
    return { nodes: [], error: "Defina um único início e conecte todas as etapas." };
  const ordered: WorkflowNode[] = [];
  const seen = new Set<string>();
  let current: string | undefined = starts[0]!.id;
  while (current && !seen.has(current)) {
    seen.add(current);
    ordered.push(nodes.get(current)!);
    current = outgoing.get(current);
  }
  if (current || ordered.length !== nodes.size)
    return { nodes: [], error: "O fluxo contém um ciclo ou etapas desconectadas." };
  return { nodes: ordered, error: null };
}

export function workflowError(flow: ScheduledWorkflow): string | null {
  if (flow.name.trim().length < 2) return "Dê um nome ao fluxo.";
  if (flow.nodes.length > 32) return "Use até 32 etapas por fluxo.";
  const order = workflowOrder(flow);
  if (order.error) return order.error;
  let sql = false,
    report = false,
    compared = false;
  let finalizing = false,
    generated = false;
  for (const node of order.nodes) {
    if (["generate_report", "open_report", "completion_modal"].includes(node.kind)) {
      finalizing = true;
      if (node.kind === "generate_report") generated = true;
      if (node.kind === "open_report" && !generated)
        return "Adicione Gerar relatório antes de Abrir relatório final.";
      continue;
    }
    if (finalizing) return "Coloque as ações de finalização depois das etapas da automação.";
    const { start_days_ago: start, end_days_ago: end } = node.options;
    if (
      ![start, end].every((value) => Number.isInteger(value) && value >= 0 && value <= 30) ||
      start < end
    )
      return "Confira o período da consulta. Use de 0 a 30 dias anteriores.";
    if (node.kind === "sql") {
      sql = true;
      compared = false;
    } else if (node.kind === "novelis_report") {
      report = true;
      compared = false;
    } else if (node.kind === "compare") {
      if (!sql || !report) return "Consulte o SQL e o relatório Novelis antes de comparar.";
      compared = true;
    } else if (["files", "pdf", "xml", "proof", "tickets"].includes(node.kind)) {
      if (!sql) return "Consulte o SQL antes de processar os documentos.";
      if (node.kind === "tickets" && !compared)
        return "Compare a consulta SQL com o relatório Novelis antes de abrir chamados.";
    }
  }
  return null;
}

export function initialWorkflow(days = 0): ScheduledWorkflow {
  const kinds: WorkflowKind[] = ["novelis_report", "sql", "compare", "pdf", "xml", "tickets"];
  const nodes = kinds.map((kind, index) => ({
    id: crypto.randomUUID(),
    kind,
    position: { x: index * 230, y: 150 },
    options: { start_days_ago: days, end_days_ago: 0 },
  }));
  return {
    version: 1,
    name: "Fluxo de abertura",
    nodes,
    edges: nodes.slice(1).map((node, index) => ({ source: nodes[index]!.id, target: node.id })),
  };
}

export function workflowPeriod(options: WorkflowOptions) {
  if (!options.start_days_ago && !options.end_days_ago) return "Dia atual";
  if (options.start_days_ago === options.end_days_ago)
    return `${options.start_days_ago} dia(s) atrás`;
  return `De ${options.start_days_ago} dia(s) atrás até ${options.end_days_ago ? `${options.end_days_ago} dia(s) atrás` : "hoje"}`;
}
