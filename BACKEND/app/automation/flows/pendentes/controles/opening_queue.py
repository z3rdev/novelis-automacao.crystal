"""Carry previously verified unopened CT-es into automatic opening workflows."""

from datetime import UTC, datetime
from pathlib import Path

from app.automation.cancellation import run_blocking
from app.automation.flows.flow_events import emit_step
from app.infrastructure.json_store import read_json, write_json
from app.infrastructure.operations_store import OperationsStore
from app.infrastructure.pending_queue import PendingQueue, access_key, cte_number
from app.domain.cte_authorization import authorization_status
from app.services.pending_authorization import refresh_queue_authorization


def uses_opening_queue(request):
    if any(getattr(request, name, None) for name in (
        "manual_ctes", "manual_spreadsheet", "sample_cte", "sample_documento", "sample_filial"
    )):
        return False
    if request.flow == "workflow":
        return request.workflow is not None and any(node.kind == "tickets" for node in request.workflow.nodes)
    return request.flow == "pendentes" and request.execution_scope in {"full", "chamados"}


def merge_queue_rows(current, pending):
    merged = {cte_number(row): row for row in pending if cte_number(row) and authorization_status(row) != "N"}
    for row in current:
        number = cte_number(row)
        if not number:
            continue
        if authorization_status(row) == "N":
            merged.pop(number, None)
            continue
        previous = merged.get(number, {})
        # Fresh SQL values win. Keep the verified key when an older SQL shape lacks it.
        if not access_key(row) and access_key(previous):
            row = {**row, "cteId": access_key(previous)}
        merged[number] = row
    return list(merged.values())


def _source_with_queue(settings, source, run_id, db_config):
    path = getattr(settings, "novelis_sqlite_path", None)
    if not path:
        return source, 0
    store = OperationsStore(Path(path))
    try:
        repository = PendingQueue(store)
        pending = refresh_queue_authorization(repository, db_config, repository.rows())
    finally:
        store.close()
    if not pending:
        return source, 0
    payload = read_json(source, {})
    current = payload if isinstance(payload, list) else payload.get("rows", [])
    rows = merge_queue_rows(current, pending)
    added = len({cte_number(row) for row in rows} - {cte_number(row) for row in current})
    output = source.parent / f"opening-queue-{run_id}.json"
    write_json(output, {
        "generatedAt": datetime.now(UTC).isoformat(),
        "sourceKind": "sql_with_opening_queue",
        "sourceFile": str(source),
        "queueEligible": False,
        "total": len(rows),
        "rows": rows,
    })
    return output, added


async def include_opening_queue(settings, source, request, emit, run_id, db_config=None):
    if source is None or not uses_opening_queue(request):
        return source
    output, added = await run_blocking(_source_with_queue, settings, source, run_id, db_config or {})
    if output != source:
        await emit_step(emit, run_id, "pendentes.queue_loaded",
                        f"Fila de abertura: {added} CT-e(s) pendente(s) adicionados à consulta SQL.",
                        {"querySource": "fila", "carried": added, "sourceJson": str(output)})
    return output
