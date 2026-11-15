import { useRef, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MarkerType,
  addEdge,
  useNodesState,
  useEdgesState,
  type Connection,
  type Edge,
  type ReactFlowInstance,
} from "@xyflow/react";
import { LayoutGrid, Plus, Save, Trash2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  initialWorkflow,
  workflowError,
  workflowOrder,
  type ScheduledWorkflow,
  type WorkflowKind,
} from "@/services/scheduled-workflow";
import { workflowCatalog } from "./catalog";
import { WorkflowCard, type CargoNode } from "./workflow-node";
import { NodeSettings } from "./node-settings";
import "@xyflow/react/dist/style.css";
import "./workflow-editor.css";

const nodeTypes = { cargo: WorkflowCard };
const edgeDefaults = {
  type: "smoothstep",
  markerEnd: { type: MarkerType.ArrowClosed, color: "#8395a7" },
};

interface Props {
  initial?: ScheduledWorkflow | null;
  days: number;
  onSave(flow: ScheduledWorkflow): void;
  onClose(): void;
}

export function WorkflowEditor({ initial, days, onSave, onClose }: Props) {
  const [seed] = useState(() => initial ?? initialWorkflow(days));
  const [name, setName] = useState(seed.name);
  const [nodes, setNodes, onNodesChange] = useNodesState<CargoNode>(
    seed.nodes.map((node) => ({
      id: node.id,
      type: "cargo",
      position: node.position,
      data: { kind: node.kind, options: node.options },
    })),
  );
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(
    seed.edges.map((edge, index) => ({ ...edge, id: `edge-${index}` })),
  );
  const [selected, setSelected] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<string | null>(null);
  const canvas = useRef<ReactFlowInstance<CargoNode, Edge> | null>(null);
  const flow: ScheduledWorkflow = {
    version: 1,
    name: name.trim(),
    nodes: nodes.map((node) => ({
      id: node.id,
      kind: node.data.kind,
      position: node.position,
      options: node.data.options,
    })),
    edges: edges.map((edge) => ({ source: edge.source, target: edge.target })),
  };
  const error = workflowError(flow);
  const active = nodes.find((node) => node.id === selected);

  const add = (kind: WorkflowKind) => {
    const id = crypto.randomUUID();
    const order = workflowOrder(flow);
    const tail = !order.error ? order.nodes.at(-1) : undefined;
    const position = tail
      ? { x: tail.position.x + 230, y: tail.position.y }
      : { x: 40, y: nodes.length * 120 };
    setNodes((previous) => [
      ...previous,
      {
        id,
        type: "cargo",
        position,
        data: {
          kind,
          options: { start_days_ago: days, end_days_ago: 0 },
        },
      },
    ]);
    if (tail)
      setEdges((previous) =>
        addEdge({ id: crypto.randomUUID(), source: tail.id, target: id }, previous),
      );
    setSelected(id);
    setSelectedEdge(null);
    requestAnimationFrame(
      () =>
        void canvas.current?.setCenter(position.x + 92, position.y + 40, {
          zoom: 1,
          duration: 250,
        }),
    );
  };
  const remove = () => {
    const before = edges.find((edge) => edge.target === selected);
    const after = edges.find((edge) => edge.source === selected);
    setEdges((previous) => {
      const kept = previous.filter((edge) => edge.source !== selected && edge.target !== selected);
      return before && after
        ? addEdge({ id: crypto.randomUUID(), source: before.source, target: after.target }, kept)
        : kept;
    });
    setNodes((previous) => previous.filter((node) => node.id !== selected));
    setSelected(null);
  };
  const validConnection = (connection: Connection | Edge) => {
    if (connection.source === connection.target) return false;
    const candidate = [...edges, { ...connection, id: "candidate" }];
    const outgoing = new Map<string, string>();
    const incoming = new Set<string>();
    for (const edge of candidate) {
      if (outgoing.has(edge.source) || incoming.has(edge.target)) return false;
      outgoing.set(edge.source, edge.target);
      incoming.add(edge.target);
    }
    const visited = new Set<string>();
    let current: string | undefined = connection.source;
    while (current && !visited.has(current)) {
      visited.add(current);
      current = outgoing.get(current);
    }
    return !current;
  };
  const arrange = () => {
    const order = workflowOrder(flow);
    const positions = new Map(
      (order.error ? flow.nodes : order.nodes).map((node, index) => [
        node.id,
        { x: index * 230, y: 150 },
      ]),
    );
    setNodes((previous) =>
      previous.map((node) => ({ ...node, position: positions.get(node.id)! })),
    );
    requestAnimationFrame(() => void canvas.current?.fitView({ padding: 0.15, duration: 250 }));
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        className="workflow-editor"
        onOpenAutoFocus={(event) => event.preventDefault()}
      >
        <DialogHeader className="border-b px-5 py-4 pr-14">
          <DialogTitle>Editor de fluxo</DialogTitle>
          <DialogDescription>
            Arraste os nós e conecte as etapas na ordem da execução.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-wrap items-center gap-3 border-b px-5 py-3">
          <Label htmlFor="workflow-name">Fluxo</Label>
          <Input
            id="workflow-name"
            value={name}
            maxLength={100}
            onChange={(event) => setName(event.target.value)}
            className="h-9 w-64"
          />
          <Button type="button" variant="outline" size="sm" onClick={arrange}>
            <LayoutGrid />
            Organizar
          </Button>
          <span className="ml-auto text-xs text-muted-foreground">{nodes.length} etapas</span>
        </div>
        <div className="workflow-workspace">
          <aside className="workflow-palette space-y-2">
            {(
              Object.entries(workflowCatalog) as [
                WorkflowKind,
                (typeof workflowCatalog)[WorkflowKind],
              ][]
            ).map(([kind, item]) => (
              <button
                type="button"
                key={kind}
                disabled={nodes.length >= 32}
                onClick={() => add(kind)}
                className="flex w-full items-center gap-2 rounded-md border bg-card px-2.5 py-3 text-left text-xs transition-colors hover:border-primary/40 hover:bg-primary/5 disabled:opacity-50"
              >
                <item.icon className="h-4 w-4 shrink-0 text-primary" />
                <span className="flex-1">{item.label}</span>
                <Plus className="h-3 w-3 text-muted-foreground" />
              </button>
            ))}
          </aside>
          <div className="workflow-canvas">
            <ReactFlow<CargoNode, Edge>
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={(connection) => setEdges((previous) => addEdge(connection, previous))}
              isValidConnection={validConnection}
              defaultEdgeOptions={edgeDefaults}
              onInit={(instance) => {
                canvas.current = instance;
              }}
              fitView
              fitViewOptions={{ padding: 0.15 }}
              minZoom={0.25}
              maxZoom={1.75}
              deleteKeyCode={null}
              onNodeClick={(_, node) => {
                setSelected(node.id);
                setSelectedEdge(null);
              }}
              onEdgeClick={(_, edge) => {
                setSelectedEdge(edge.id);
                setSelected(null);
              }}
              onPaneClick={() => {
                setSelected(null);
                setSelectedEdge(null);
              }}
            >
              <Background gap={20} size={1} color="#c5ced7" />
              <Controls showInteractive={false} />
            </ReactFlow>
          </div>
          {selectedEdge ? (
            <aside className="workflow-settings">
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => {
                  setEdges((previous) => previous.filter((edge) => edge.id !== selectedEdge));
                  setSelectedEdge(null);
                }}
              >
                <Trash2 />
                Remover conexão
              </Button>
            </aside>
          ) : (
            <NodeSettings
              node={active}
              onRemove={remove}
              onOptions={(options) =>
                setNodes((previous) =>
                  previous.map((node) =>
                    node.id === selected ? { ...node, data: { ...node.data, options } } : node,
                  ),
                )
              }
            />
          )}
        </div>
        <footer className="flex items-center gap-3 border-t px-5 py-3">
          {error && (
            <p role="alert" className="mr-auto text-xs text-destructive">
              {error}
            </p>
          )}
          <Button type="button" variant="outline" className="ml-auto" onClick={onClose}>
            Cancelar
          </Button>
          <Button type="button" onClick={() => onSave(flow)} disabled={!!error}>
            <Save />
            Usar no agendamento
          </Button>
        </footer>
      </DialogContent>
    </Dialog>
  );
}
