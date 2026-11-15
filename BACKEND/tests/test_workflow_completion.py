import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from openpyxl import load_workbook
from pydantic import ValidationError

from app.domain.models import RunSnapshot, RunStartRequest
from app.domain.scheduled_workflow import ScheduledWorkflow
from app.infrastructure.event_bus import EventBus
from app.infrastructure.operations_store import OperationsStore
from app.services.execution_reports.service import ExecutionReports
from app.services.hub_service import HubService
from app.services.workflow_finalization import finalize_workflow
from app.services.workflow_view import workflow_view


def graph(*kinds):
    nodes = [
        {"id": f"node-{i}", "kind": kind, "position": {"x": i * 230, "y": 0}}
        for i, kind in enumerate(kinds)
    ]
    return {
        "name": "Fluxo com finalização",
        "nodes": nodes,
        "edges": [
            {"source": nodes[i - 1]["id"], "target": node["id"]}
            for i, node in enumerate(nodes)
            if i
        ],
    }


@pytest.mark.parametrize("kinds", [("open_report",), ("generate_report", "sql")])
def test_finalization_dependencies_are_validated(kinds):
    with pytest.raises(ValidationError):
        ScheduledWorkflow.model_validate(graph(*kinds))


def test_workflow_view_keeps_each_node_in_connection_order():
    definition = graph("sql", "sql", "pdf", "generate_report")
    definition["nodes"].reverse()
    events = [
        {"kind": "run.started", "payload": {"workflow": definition}},
        {"kind": "workflow.node.started", "payload": {"node_id": "node-0"}},
        {
            "kind": "workflow.node.completed",
            "payload": {"node_id": "node-0", "done": 2, "total": 2},
        },
        {"kind": "workflow.node.started", "payload": {"node_id": "node-1"}},
        {"kind": "pendentes.sql_loaded", "message": "Consulta SQL", "payload": {"total": 3}},
    ]
    view = workflow_view({"status": "running"}, events)
    assert [node["id"] for node in view["nodes"]] == [f"node-{i}" for i in range(4)]
    assert [node["state"] for node in view["nodes"]] == [
        "concluida",
        "executando",
        "aguardando",
        "aguardando",
    ]
    assert view["current_node_id"] == "node-1"
    assert view["completed"] == 1 and view["nodes"][1]["total"] == 3
    failed = workflow_view({"status": "failed"}, events)
    assert failed["nodes"][1]["state"] == "falhou"
    assert failed["nodes"][2]["state"] == "ignorada"


def test_long_run_retains_its_graph_after_ui_logs_exceed_limit(tmp_path):
    store = OperationsStore(tmp_path / "operations.sqlite")
    store.initialize()
    snapshot = RunSnapshot(flow="workflow", status="running", started_at=datetime.now(UTC))
    bus = EventBus(store=store)

    async def exercise():
        await bus.publish(
            "Start",
            run_id=snapshot.id,
            kind="run.started",
            payload={"workflow": graph("sql", "pdf")},
        )
        await bus.publish(
            "SQL",
            run_id=snapshot.id,
            kind="workflow.node.started",
            payload={"node_id": "node-0", "stage": "consulta"},
        )
        with store.connection() as db:
            import json

            db.executemany(
                "INSERT INTO execution_events(run_id,payload) VALUES (?,?)",
                [
                    (snapshot.id, json.dumps({"kind": "progress", "machine_id": store.machine_id}))
                    for _ in range(1001)
                ],
            )
        hub = HubService(
            SimpleNamespace(backend_root=tmp_path / "BACKEND"),
            None,
            store,
            SimpleNamespace(current=AsyncMock(return_value=snapshot)),
            bus,
        )
        value = await hub.run()
        assert len(value["workflow"]["nodes"]) == 2
        assert value["workflow"]["nodes"][0]["state"] == "executando"

    try:
        asyncio.run(exercise())
    finally:
        store.close()


def test_report_and_ui_finalizers_run_after_business_completion(tmp_path):
    store = OperationsStore(tmp_path / "shared.sqlite")
    store.initialize()
    storage = SimpleNamespace(
        publish=lambda *_: (_ for _ in ()).throw(RuntimeError("offline")),
        retrieve=lambda value, path: path,
    )
    reports = ExecutionReports(
        SimpleNamespace(backend_root=tmp_path / "BACKEND"), {}, store, storage=storage
    )
    request = RunStartRequest(
        flow="workflow",
        dry_run=False,
        workflow=graph("generate_report", "open_report", "completion_modal"),
    )
    snapshot = RunSnapshot(flow="workflow", status="running", started_at=datetime.now(UTC))
    bus = EventBus(store=store)

    async def exercise():
        await reports.begin(snapshot, request)
        await bus.publish(
            "Start", run_id=snapshot.id, kind="run.started", payload=request.model_dump(mode="json")
        )
        finished = snapshot.model_copy(
            update={"status": "completed", "finished_at": datetime.now(UTC)}
        )
        await finalize_workflow(request, finished, bus, reports)
        await reports._job
        view = workflow_view(
            finished.model_dump(mode="json"),
            [item.model_dump(mode="json") for item in await bus.history()],
        )
        assert view["completed"] == 3
        result = view["completion"]
        assert result["ready"] and result["show_modal"] and result["open_report"]
        assert result["error"] is None and result["opened_count"] == 0
        assert reports.page()["total"] == 1
        file = reports.download(result["report_id"])
        book = load_workbook(file)
        assert book["Chamados abertos"].max_row == 1
        book.close()
        await reports.close()

    try:
        asyncio.run(exercise())
    finally:
        store.close()


def test_report_failure_keeps_confirmed_counts_and_still_requests_summary():
    request = RunStartRequest(
        flow="workflow",
        dry_run=False,
        workflow=graph("generate_report", "open_report", "completion_modal"),
    )
    snapshot = RunSnapshot(
        flow="workflow",
        status="completed",
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    bus = EventBus()

    async def exercise():
        await bus.publish(
            "Save",
            run_id=snapshot.id,
            kind="novelis.save",
            payload={"ticket": {"cte": "8-10-1559", "numero": "123"}, "result": {"ok": True}},
        )
        await finalize_workflow(
            request,
            snapshot,
            bus,
            SimpleNamespace(finish=AsyncMock(side_effect=RuntimeError("private-storage-detail"))),
        )
        events = await bus.history()
        payload = events[-1].payload
        assert payload["show_modal"] and not payload["open_report"]
        assert payload["error"] and payload["opened_count"] == 1
        assert "private-storage-detail" not in str([event.model_dump() for event in events])

    asyncio.run(exercise())
