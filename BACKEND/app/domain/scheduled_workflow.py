"""Validated execution order for the visual schedule editor."""

from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

NodeKind = Literal[
    "tariffs",
    "novelis_report",
    "sql",
    "compare",
    "files",
    "pdf",
    "xml",
    "proof",
    "tickets",
    "generate_report",
    "open_report",
    "completion_modal",
]
FINALIZERS = {"generate_report", "open_report", "completion_modal"}
NODE_LABELS = {
    "tariffs": "Atualizar tarifário",
    "novelis_report": "Consultar relatório Novelis",
    "sql": "Consultar SQL",
    "compare": "Comparar com relatório Novelis",
    "files": "Verificar arquivos",
    "pdf": "Baixar PDF",
    "xml": "Baixar XML",
    "proof": "Buscar comprovante",
    "tickets": "Abrir chamado",
    "generate_report": "Gerar relatório",
    "open_report": "Abrir relatório final",
    "completion_modal": "Mostrar modal de finalização",
}
NODE_STAGES = {
    "tariffs": None,
    "novelis_report": "consulta",
    "sql": "consulta",
    "compare": "consulta",
    "files": "consulta",
    "pdf": "pdf",
    "xml": "xml",
    "proof": "comprovantes",
    "tickets": "chamados",
    "generate_report": None,
    "open_report": None,
    "completion_modal": None,
}


class Position(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x: float = Field(ge=-100000, le=100000, allow_inf_nan=False)
    y: float = Field(ge=-100000, le=100000, allow_inf_nan=False)


class NodeOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_days_ago: int = Field(default=0, ge=0, le=30)
    end_days_ago: int = Field(default=0, ge=0, le=30)

    @model_validator(mode="after")
    def check_range(self):
        if self.start_days_ago < self.end_days_ago:
            raise ValueError("O início do período deve ser anterior ou igual ao fim.")
        return self

    def period(self, today: date):
        return (
            today - timedelta(days=self.start_days_ago),
            today - timedelta(days=self.end_days_ago),
        )


class WorkflowNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    kind: NodeKind
    position: Position
    options: NodeOptions = Field(default_factory=NodeOptions)


class WorkflowEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
    target: str


class ScheduledWorkflow(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    version: Literal[1] = 1
    name: str = Field(min_length=2, max_length=100)
    nodes: list[WorkflowNode] = Field(min_length=1, max_length=32)
    edges: list[WorkflowEdge] = Field(default_factory=list, max_length=31)

    def ordered_nodes(self):
        nodes = {node.id: node for node in self.nodes}
        if len(nodes) != len(self.nodes):
            raise ValueError("Cada etapa precisa de um identificador único.")
        incoming, outgoing = {}, {}
        for edge in self.edges:
            if edge.source not in nodes or edge.target not in nodes:
                raise ValueError("Uma conexão aponta para uma etapa inexistente.")
            if edge.source in outgoing or edge.target in incoming:
                raise ValueError("Conecte as etapas em uma única sequência.")
            outgoing[edge.source], incoming[edge.target] = edge.target, edge.source
        roots = [key for key in nodes if key not in incoming]
        if len(roots) != 1:
            raise ValueError("Defina um único início e conecte todas as etapas.")
        result, visited, current = [], set(), roots[0]
        while current is not None and current not in visited:
            visited.add(current)
            result.append(nodes[current])
            current = outgoing.get(current)
        if current is not None or len(result) != len(nodes):
            raise ValueError("O fluxo contém um ciclo ou etapas desconectadas.")
        return result

    @model_validator(mode="after")
    def validate_execution(self):
        sql, report, compared = False, False, False
        finalizing, generated = False, False
        for node in self.ordered_nodes():
            if node.kind in FINALIZERS:
                finalizing = True
                if node.kind == "generate_report":
                    generated = True
                if node.kind == "open_report" and not generated:
                    raise ValueError("Adicione Gerar relatório antes de Abrir relatório final.")
                continue
            if finalizing:
                raise ValueError("Coloque as ações de finalização depois das etapas da automação.")
            if node.kind == "sql":
                sql, compared = True, False
            elif node.kind == "novelis_report":
                report, compared = True, False
            elif node.kind == "compare":
                if not sql or not report:
                    raise ValueError("Consulte o SQL e o relatório Novelis antes de comparar.")
                compared = True
            elif node.kind in {"files", "pdf", "xml", "proof", "tickets"}:
                if not sql:
                    raise ValueError(f"Consulte o SQL antes de {NODE_LABELS[node.kind].lower()}.")
                if node.kind == "tickets" and not compared:
                    raise ValueError(
                        "Compare a consulta SQL com o relatório Novelis antes de abrir chamados."
                    )
        return self
