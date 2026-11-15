"""Project the saved node graph and durable lifecycle events into live cards."""

from app.domain.scheduled_workflow import NODE_LABELS, ScheduledWorkflow


def workflow_view(snapshot, events):
    definition = next(
        (
            event.get("payload", {}).get("workflow")
            for event in events
            if event.get("kind") == "run.started"
        ),
        None,
    )
    if not definition:
        return None
    graph = ScheduledWorkflow.model_validate(definition)
    nodes = {
        node.id: {
            "id": node.id,
            "kind": node.kind,
            "label": NODE_LABELS[node.kind],
            "options": node.options.model_dump(),
            "state": "aguardando",
            "done": 0,
            "total": 0,
            "detail": "",
            "started_at": None,
            "finished_at": None,
        }
        for node in graph.ordered_nodes()
    }
    active, completion = None, None
    for event in events:
        kind, payload = event.get("kind", ""), event.get("payload") or {}
        if kind == "workflow.finished":
            completion = {**payload, "ready": True}
        elif kind.startswith("workflow.node.") and payload.get("node_id") in nodes:
            active = payload["node_id"]
            node = nodes[active]
            node["detail"] = event.get("message", "")
            if kind == "workflow.node.started":
                node.update(state="executando", started_at=event.get("created_at"))
            elif kind == "workflow.node.completed":
                node.update(
                    state="concluida",
                    finished_at=event.get("created_at"),
                    done=payload.get("done", 1),
                    total=payload.get("total", 1),
                )
            elif kind == "workflow.node.failed":
                node.update(state="falhou", finished_at=event.get("created_at"))
        elif active and nodes[active]["state"] == "executando":
            node = nodes[active]
            if payload.get("total") is not None:
                node["total"] = int(payload["total"])
            if payload.get("current"):
                node["done"] = max(0, int(payload["current"]) - 1)
            if kind.endswith((".saved", ".reused")) or kind in {
                "novelis.save",
                "novelis.chamado_exists",
            }:
                node["done"] += 1
            if event.get("message"):
                node["detail"] = event["message"]
    for node in nodes.values():
        if snapshot["status"] == "stopping" and node["state"] == "executando":
            node["state"] = "parando"
        elif snapshot["status"] == "cancelled" and node["state"] not in {"concluida", "falhou"}:
            node["state"] = "cancelada"
        elif snapshot["status"] == "failed":
            if node["state"] == "executando":
                node["state"] = "falhou"
            elif node["state"] == "aguardando":
                node["state"] = "ignorada"
    return {
        "name": graph.name,
        "current_node_id": active,
        "nodes": list(nodes.values()),
        "completed": sum(node["state"] == "concluida" for node in nodes.values()),
        "total": len(nodes),
        "completion": completion,
    }
