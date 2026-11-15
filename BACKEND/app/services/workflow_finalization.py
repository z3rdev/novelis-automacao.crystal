import asyncio

from app.domain.scheduled_workflow import FINALIZERS, NODE_LABELS
from app.services.execution_reports.models import entries
from app.services.execution_reports.repository import ReportRepository


async def finalize_workflow(request, snapshot, events, reports):
    nodes = [node for node in request.workflow.ordered_nodes() if node.kind in FINALIZERS]
    result, error, open_report = None, None, False

    async def generate():
        if reports is None:
            raise RuntimeError("Serviço de relatórios indisponível.")
        return await reports.finish(snapshot)

    try:
        if snapshot.status != "completed" or not any(
            node.kind == "generate_report" for node in nodes
        ):
            result = await generate() if reports else None
        if snapshot.status == "completed":
            for node in nodes:
                payload = {
                    "node_id": node.id,
                    "node_kind": node.kind,
                    "stage": None,
                    "workflow_name": request.workflow.name,
                }
                await events.publish(
                    NODE_LABELS[node.kind],
                    run_id=snapshot.id,
                    kind="workflow.node.started",
                    payload=payload,
                )
                try:
                    if node.kind == "generate_report":
                        result = await generate()
                        if result is None:
                            raise RuntimeError("Registro da execução indisponível.")
                    elif node.kind == "open_report":
                        if not result or not result.get("daily_reports"):
                            raise RuntimeError("O relatório final não está disponível.")
                        open_report = True
                    await events.publish(
                        f"{NODE_LABELS[node.kind]} concluído.",
                        run_id=snapshot.id,
                        kind="workflow.node.completed",
                        payload={**payload, "done": 1, "total": 1},
                    )
                except Exception:  # noqa: BLE001 - reporting failures preserve confirmed fiscal results.
                    error = "Não foi possível preparar o relatório final. As aberturas confirmadas foram preservadas."
                    await events.publish(
                        error,
                        run_id=snapshot.id,
                        kind="workflow.node.failed",
                        level="warn",
                        payload=payload,
                    )
    except Exception:  # noqa: BLE001 - redact storage details at the UI boundary.
        error = "O relatório final está pendente. Confira a disponibilidade do banco compartilhado."
    daily = ((result or {}).get("daily_reports") or [None])[-1]
    opened_count, existing_count = (
        (result or {}).get("opened_count", 0),
        (result or {}).get("existing_count", 0),
    )
    if result is None:
        history = (
            await asyncio.to_thread(ReportRepository(events.store).events, snapshot.id)
            if events.store
            else [item.model_dump(mode="json") for item in await events.history()]
        )
        opened, existing = entries(history)
        opened_count, existing_count = len(opened), len(existing)
    await events.publish(
        "Finalização do fluxo personalizado concluída.",
        run_id=snapshot.id,
        kind="workflow.finished",
        payload={
            "open_report": open_report,
            "show_modal": any(node.kind == "completion_modal" for node in nodes),
            "report_id": daily["id"] if daily else None,
            "report_date": daily["report_date"] if daily else None,
            "opened_count": opened_count,
            "existing_count": existing_count,
            "error": error,
        },
    )
