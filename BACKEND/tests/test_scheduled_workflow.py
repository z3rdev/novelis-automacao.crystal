import asyncio
from copy import deepcopy
from datetime import date, datetime, timedelta
from itertools import pairwise
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from openpyxl import Workbook
from pydantic import ValidationError

from app.automation.flows.pendentes.steps.pendentes import PendentesFlow
from app.automation.flows.scheduled_workflow.runner import ScheduledWorkflowRunner
from app.domain.hub_features import ScheduleInput
from app.domain.models import RunStartRequest
from app.domain.run_state import RunState
from app.domain.scheduled_workflow import NodeOptions, ScheduledWorkflow
from app.infrastructure.event_bus import EventBus
from app.infrastructure.operations_store import OperationsStore
from app.services.automation_service import AutomationService
from app.services.execution_reports.service import ExecutionReports
from app.services.hub_views import run_view


def graph(*kinds):
    nodes = [
        {
            "id": f"step-{index}",
            "kind": kind,
            "position": {"x": index * 230, "y": 100},
            "options": {"start_days_ago": 2, "end_days_ago": 0},
        }
        for index, kind in enumerate(kinds)
    ]
    return {
        "version": 1,
        "name": "Abertura da manhã",
        "nodes": nodes,
        "edges": [
            {"source": before["id"], "target": after["id"]} for before, after in pairwise(nodes)
        ],
    }


@pytest.mark.parametrize(
    "kinds",
    [
        ("novelis_report", "sql", "compare", "pdf", "xml", "tickets"),
        ("sql", "novelis_report", "compare", "xml", "pdf", "proof", "tickets"),
        ("sql", "pdf"),
        ("novelis_report",),
        ("sql", "files"),
    ],
)
def test_graph_preserves_the_connected_execution_order(kinds):
    value = ScheduledWorkflow.model_validate(graph(*kinds))
    value.nodes.reverse()  # Storage/visual order never overrides the connections.
    assert tuple(node.kind for node in value.ordered_nodes()) == kinds


@pytest.mark.parametrize(
    "kinds",
    [
        ("pdf",),
        ("compare",),
        ("sql", "compare"),
        ("sql", "tickets"),
        ("novelis_report", "sql", "compare", "sql", "tickets"),
        ("novelis_report", "sql", "compare", "novelis_report", "tickets"),
    ],
)
def test_missing_inputs_and_stale_comparison_are_rejected(kinds):
    with pytest.raises(ValidationError):
        ScheduledWorkflow.model_validate(graph(*kinds))


@pytest.mark.parametrize("change", ["disconnected", "cycle", "duplicate", "missing", "branch"])
def test_invalid_connections_are_rejected(change):
    value = graph("sql", "files", "pdf")
    if change == "disconnected":
        value["edges"].pop()
    elif change == "cycle":
        value["edges"].append({"source": "step-2", "target": "step-0"})
    elif change == "duplicate":
        value["nodes"][1]["id"] = "step-0"
    elif change == "missing":
        value["edges"][0]["target"] = "missing"
    else:
        value["edges"][1]["source"] = "step-0"
    with pytest.raises(ValidationError):
        ScheduledWorkflow.model_validate(value)


def test_periods_are_relative_to_the_run_day_and_bounded():
    options = NodeOptions(start_days_ago=2, end_days_ago=2)
    assert options.period(date(2026, 11, 14)) == (date(2026, 11, 12), date(2026, 11, 12))
    for values in ({"start_days_ago": 31}, {"start_days_ago": 0, "end_days_ago": 2}):
        with pytest.raises(ValidationError):
            NodeOptions(**values)
    with pytest.raises(ValidationError):
        ScheduleInput(name="Custom", flow="personalizado")
    assert ScheduleInput(name="Antigo").workflow is None


def test_only_supported_actions_and_options_are_accepted():
    value = graph("sql")
    value["nodes"][0]["options"]["script"] = "anything"
    with pytest.raises(ValidationError):
        ScheduledWorkflow.model_validate(value)
    value = graph("sql")
    value["nodes"][0]["kind"] = "execute_script"
    with pytest.raises(ValidationError):
        ScheduledWorkflow.model_validate(value)


@pytest.mark.parametrize("finalize", [False, True])
@pytest.mark.parametrize("carried", [False, True])
def test_normal_entry_executes_custom_order_and_generates_daily_report(tmp_path, monkeypatch, finalize, carried):
    from app.services.execution_reports.models import ticket

    backend = tmp_path / "BACKEND"
    backend.mkdir()
    settings = SimpleNamespace(
        backend_root=backend, novelis_sqlite_path=None, consulta_browser_headless=False
    )
    legacy = SimpleNamespace(
        pendentes=lambda: {"stopOnError": True},
        rodopar_pdf=dict,
        xml_sefaz=dict,
        comprovante_local=dict,
        chamado_novelis=lambda: {"chamadosLogFile": str(tmp_path / "ledger.json")},
        consulta_db=lambda: {"enabled": True},
        get=lambda key, default="": default,
    )
    rows = [
        {"filial": "8", "serie": "10", "documento": str(doc), "cteId": str(doc).zfill(44)}
        for doc in (1559, 1560)
    ]
    state = {"pdf": False, "xml": False}
    calls, periods = [], []

    async def download(config, period, output):
        calls.append("report")
        periods.append(period)
        output.parent.mkdir(parents=True, exist_ok=True)
        book = Workbook()
        book.active.append(["ID", "SERIE", "NCT", "CHAMADO"])
        book.active.append([rows[0]["cteId"], "10", "1559", "202611140001"])
        book.save(output)
        book.close()
        return {
            "file": output,
            "suggestedName": output.name,
            "sourceUrl": "https://novelis.wtmh.com.br/custom/relatorio_cte_xml",
            "dateRange": period,
        }

    def sql(config, days, start, end):
        calls.append("sql")
        periods.append((start, end))
        return SimpleNamespace(
            rows=deepcopy(rows[:1] if carried else rows), source_file="SQL", source={"generatedAt": "fixture"}
        )

    def evidence(builder, wanted, *_args):
        return [
            {
                "pdfFile": "verified.pdf" if state["pdf"] else "",
                "xmlFile": "verified.xml" if state["xml"] else "",
                "comprovanteOk": True,
            }
            for _ in wanted
        ]

    async def pdf(*args):
        calls.append("pdf")
        state["pdf"] = True

    async def xml(*args):
        calls.append("xml")
        state["xml"] = True

    async def tickets(flow, browser, config, plan, request, run_id, *_args):
        calls.append("tickets")
        assert browser is None and plan["prontosChamado"] == ["8-10-1560"]
        assert plan["rows"][0]["__novelis"]["prechecked"] is True
        await flow.emit(
            "Confirmado (integração controlada).",
            kind="novelis.save",
            run_id=run_id,
            payload={"ticket": ticket(plan["rows"][0], "202611140002"), "result": {"ok": True}},
        )

    monkeypatch.setattr("app.automation.flows.scheduled_workflow.runner.download_report", download)
    monkeypatch.setattr(
        "app.automation.flows.scheduled_workflow.runner.select_pdf_runner", lambda _: pdf
    )
    monkeypatch.setattr(
        "app.automation.flows.pendentes.steps.pendentes.fetch_last_5_days_rows", sql
    )
    monkeypatch.setattr(
        "app.automation.flows.pendentes.steps.pendentes.annotate_plan", lambda plan, _: plan
    )
    monkeypatch.setattr("app.automation.flows.pendentes.controles.plan.scan_evidence", evidence)
    monkeypatch.setattr("app.services.chamados_catalog.current_catalog", lambda _: None)
    monkeypatch.setattr(PendentesFlow, "_run_xml_sefaz", xml)
    monkeypatch.setattr(PendentesFlow, "_run_chamados", tickets)
    monkeypatch.setattr("app.services.automation_service.clean_capture_roots", lambda *_: {})
    store = OperationsStore(tmp_path / "shared.sqlite")
    store.initialize()
    if carried:
        from app.infrastructure.pending_queue import PendingQueue
        settings.novelis_sqlite_path = store.path
        PendingQueue(store).ingest({"rows": [rows[1]], "generatedAt": "2026-11-13T12:00:00Z"}, "older-query")
    storage = SimpleNamespace(publish=lambda *_: (_ for _ in ()).throw(RuntimeError("offline")))
    reports = ExecutionReports(settings, legacy, store, storage=storage)
    bus, browser = EventBus(store=store), AsyncMock()
    automation = AutomationService(settings, legacy, None, bus, RunState(store), browser, reports)
    kinds = ["novelis_report", "sql", "compare", "xml", "pdf", "tickets"]
    if finalize:
        kinds += ["generate_report", "open_report", "completion_modal"]
    definition = graph(*kinds)
    definition["nodes"][0]["options"] = {"start_days_ago": 0, "end_days_ago": 0}

    async def exercise():
        await automation.start(RunStartRequest(flow="workflow", workflow=definition, dry_run=False))
        await automation._task
        if reports._job:
            await reports._job
        snapshot = await automation.current()
        assert snapshot.status == "completed", snapshot.message
        assert calls == ["report", "sql", "xml", "pdf", "tickets"]
        assert reports.page()["rows"][0]["opened_count"] == 1
        history = [event.model_dump(mode="json") for event in await bus.history()]
        assert any(event["kind"] == "pendentes.queue_loaded" for event in history) is carried
        completed = [
            event["payload"]["node_kind"]
            for event in history
            if event["kind"] == "workflow.node.completed"
        ]
        assert completed == kinds
        assert sum(event["kind"] == "novelis_relatorio.http_download" for event in history) == 1
        view = run_view(snapshot.model_dump(mode="json"), history)
        assert view["flow"] == "personalizado"
        assert view["workflow"]["completion"]["open_report"] is finalize
        assert view["workflow"]["completion"]["show_modal"] is finalize
        assert (
            next(stage for stage in view["stages"] if stage["id"] == "comprovantes")["state"]
            == "ignorada"
        )
        assert [call[0] for call in browser.mock_calls if not call[0].startswith("__")] == ["close"]
        today = datetime.now().astimezone().date()
        assert periods[0]["startBR"] == today.strftime("%d/%m/%Y")
        assert periods[1] == (today - timedelta(days=2), today)
        await reports.close()

    try:
        asyncio.run(exercise())
    finally:
        store.close()


def test_dry_run_never_queries_or_opens_documents(tmp_path, monkeypatch):
    legacy = SimpleNamespace(
        pendentes=dict,
        chamado_novelis=dict,
        rodopar_pdf=dict,
        xml_sefaz=dict,
        comprovante_local=dict,
    )
    emit = AsyncMock()
    runner = ScheduledWorkflowRunner(
        SimpleNamespace(backend_root=tmp_path / "BACKEND"), legacy, None, emit
    )
    monkeypatch.setattr(runner, "sql", AsyncMock(side_effect=AssertionError("SQL must not run")))
    request = RunStartRequest(flow="workflow", workflow=graph("sql", "pdf"), dry_run=True)
    assert asyncio.run(runner.run(None, request, "dry"))["dry_run"] is True


def test_failed_node_stops_the_sequence_and_keeps_earlier_results(tmp_path, monkeypatch):
    legacy = SimpleNamespace(
        pendentes=dict,
        chamado_novelis=dict,
        rodopar_pdf=dict,
        xml_sefaz=dict,
        comprovante_local=dict,
    )
    emit = AsyncMock()
    runner = ScheduledWorkflowRunner(
        SimpleNamespace(backend_root=tmp_path / "BACKEND"), legacy, None, emit
    )
    monkeypatch.setattr(runner, "report", AsyncMock(side_effect=RuntimeError("controlled failure")))
    sql = AsyncMock()
    monkeypatch.setattr(runner, "sql", sql)
    request = RunStartRequest(
        flow="workflow", workflow=graph("novelis_report", "sql"), dry_run=False
    )
    with pytest.raises(RuntimeError, match="controlled"):
        asyncio.run(runner.run(None, request, "failure"))
    sql.assert_not_awaited()
    assert any(call.kwargs["kind"] == "workflow.node.failed" for call in emit.await_args_list)


def test_cancellation_between_nodes_does_not_start_the_next_action(tmp_path, monkeypatch):
    from app.automation.cancellation import RunCancellation, cancellation_scope

    legacy = SimpleNamespace(
        pendentes=dict,
        chamado_novelis=dict,
        rodopar_pdf=dict,
        xml_sefaz=dict,
        comprovante_local=dict,
    )
    document = AsyncMock()

    async def exercise():
        cancellation = RunCancellation()

        async def emit(message, **event):
            if event["kind"] == "workflow.node.completed":
                cancellation.request_cancel()

        runner = ScheduledWorkflowRunner(
            SimpleNamespace(backend_root=tmp_path / "BACKEND"), legacy, None, emit
        )
        monkeypatch.setattr(runner, "sql", AsyncMock())
        monkeypatch.setattr(runner, "documents", document)
        request = RunStartRequest(flow="workflow", workflow=graph("sql", "pdf"), dry_run=False)
        with cancellation_scope(cancellation), pytest.raises(asyncio.CancelledError):
            await runner.run(None, request, "cancelled")
        await cancellation.drain()

    asyncio.run(exercise())
    document.assert_not_awaited()


def test_proof_search_can_run_before_documents_are_downloaded(tmp_path, monkeypatch):
    legacy = SimpleNamespace(
        pendentes=dict,
        chamado_novelis=dict,
        rodopar_pdf=dict,
        xml_sefaz=dict,
        comprovante_local=dict,
    )
    runner = ScheduledWorkflowRunner(
        SimpleNamespace(backend_root=tmp_path / "BACKEND"), legacy, None, AsyncMock()
    )
    plan = {
        "checked": [{"cte": "8-10-1559", "row": {}, "evidence": {"comprovanteOk": False}}],
        "faltandoPdf": ["8-10-1559"],
        "faltandoXml": ["8-10-1559"],
        "faltandoComprovante": [],
    }
    monkeypatch.setattr(runner, "ensure_plan", AsyncMock(return_value=plan))
    find = AsyncMock()
    monkeypatch.setattr(runner.flow, "_run_comprovantes", find)
    runner.proofs, runner.config, runner.run_id, runner.request = {}, {}, "proof", RunStartRequest()
    node = ScheduledWorkflow.model_validate(graph("sql", "proof")).nodes[1]
    asyncio.run(runner.documents(node))
    assert find.await_args.args[1]["faltandoComprovante"] == ["8-10-1559"]
