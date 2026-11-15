import asyncio
from itertools import pairwise
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.automation.flows.scheduled_workflow.runner import ScheduledWorkflowRunner
from app.automation.flows.scheduled_workflow.tariffs import refresh_tariffs
from app.domain.models import RunStartRequest
from app.services.hub_views import run_view
from app.services.tariffs.portal import PortalError
from app.services.tariffs.service import TariffService


def request(*kinds, dry_run=False):
    nodes = [
        {"id": f"step-{i}", "kind": kind, "position": {"x": 0, "y": 0}}
        for i, kind in enumerate(kinds)
    ]
    return RunStartRequest(
        flow="workflow",
        dry_run=dry_run,
        workflow={
            "name": "Atualização e consulta",
            "nodes": nodes,
            "edges": [{"source": a["id"], "target": b["id"]} for a, b in pairwise(nodes)],
        },
    )


def runner(tmp_path, emit):
    config = SimpleNamespace(
        pendentes=dict,
        chamado_novelis=dict,
        rodopar_pdf=dict,
        xml_sefaz=dict,
        comprovante_local=dict,
    )
    return ScheduledWorkflowRunner(
        SimpleNamespace(backend_root=tmp_path / "BACKEND"), config, None, emit
    )


def test_tariff_node_waits_before_sql_and_projects_its_catalog_count(tmp_path, monkeypatch):
    async def exercise():
        events, entered, release = [], asyncio.Event(), asyncio.Event()

        async def emit(message, **event):
            events.append({**event, "message": message})

        async def update(*args):
            entered.set()
            await release.wait()
            return {"total": 53}

        monkeypatch.setattr(
            "app.automation.flows.scheduled_workflow.runner.refresh_tariffs", update
        )
        value = runner(tmp_path, emit)
        sql = AsyncMock()
        monkeypatch.setattr(value, "sql", sql)
        definition = request("tariffs", "sql")
        task = asyncio.create_task(value.run(None, definition, "fixture"))
        await entered.wait()
        sql.assert_not_awaited()
        release.set()
        await task
        sql.assert_awaited_once()
        started = {"kind": "run.started", "payload": {"workflow": definition.workflow.model_dump()}}
        view = run_view(
            {
                "id": "fixture",
                "flow": "workflow",
                "status": "completed",
                "dry_run": False,
                "started_at": None,
                "finished_at": None,
                "message": "",
            },
            [started, *events],
        )["workflow"]
        assert view["nodes"][0]["label"] == "Atualizar tarifário"
        assert view["nodes"][0]["state"] == "concluida"
        assert view["nodes"][0]["done"] == view["nodes"][0]["total"] == 53

    asyncio.run(exercise())


def test_failed_tariff_update_stops_workflow_and_dry_run_never_collects(tmp_path, monkeypatch):
    update = AsyncMock(side_effect=RuntimeError("Falha controlada do tarifário"))
    monkeypatch.setattr("app.automation.flows.scheduled_workflow.runner.refresh_tariffs", update)
    value = runner(tmp_path, AsyncMock())
    sql = AsyncMock()
    monkeypatch.setattr(value, "sql", sql)
    with pytest.raises(RuntimeError, match="controlada"):
        asyncio.run(value.run(None, request("tariffs", "sql"), "failure"))
    sql.assert_not_awaited()
    update.reset_mock()
    asyncio.run(value.run(None, request("tariffs", dry_run=True), "dry"))
    update.assert_not_awaited()


class Catalog:
    enabled = True

    def __init__(self):
        self.state, self.total, self.message = "idle", 0, ""

    def initialize(self):
        pass

    def claim(self, force):
        if self.state == "running":
            return None
        self.state = "running"
        return "owned"

    def sync_status(self):
        return {"state": self.state, "total": self.total}

    def save(self, rows, cities, next_check, lease):
        self.state, self.total = "completed", len(rows)

    def fail(self, lease, message, **kwargs):
        self.state, self.message = "failed", message


def test_refresh_waits_for_import_commit_and_sanitizes_failure():
    async def exercise():
        catalog, entered, release = Catalog(), asyncio.Event(), asyncio.Event()

        async def collect(config):
            entered.set()
            await release.wait()
            return [], {}

        service = TariffService(None, catalog, collect)
        task = asyncio.create_task(service.refresh_and_wait())
        await entered.wait()
        assert not task.done() and catalog.state == "running"
        release.set()
        assert (await task)["state"] == "completed"
        service.collector = AsyncMock(side_effect=PortalError("private response fixture"))
        with pytest.raises(RuntimeError, match="catálogo anterior") as error:
            await service.refresh_and_wait()
        assert "private response" not in str(error.value)
        await service.close()

    asyncio.run(exercise())


def test_another_computers_import_is_awaited_without_starting_a_second_collector():
    async def exercise():
        catalog = Catalog()
        catalog.state = "running"
        collector = AsyncMock()
        service = TariffService(None, catalog, collector)
        task = asyncio.create_task(service.refresh_and_wait(poll_seconds=0.01))
        await asyncio.sleep(0.02)
        assert not task.done()
        catalog.state, catalog.total = "completed", 81
        assert (await task)["total"] == 81
        collector.assert_not_awaited()
        await service.close()

    asyncio.run(exercise())


def test_wait_has_a_timeout_and_cancels_only_the_owned_import():
    async def exercise():
        catalog, entered = Catalog(), asyncio.Event()

        async def collect(config):
            entered.set()
            await asyncio.Event().wait()

        service = TariffService(None, catalog, collect)
        with pytest.raises(TimeoutError):
            await service.refresh_and_wait(timeout_seconds=0.1)
        assert entered.is_set() and service._job.cancelled()
        assert catalog.state == "failed"
        await service.close()

    asyncio.run(exercise())


@pytest.mark.parametrize("failure", [RuntimeError("controlled"), asyncio.CancelledError()])
def test_workflow_collector_is_closed_on_error_or_stop(monkeypatch, failure):
    service = SimpleNamespace(refresh_and_wait=AsyncMock(side_effect=failure), close=AsyncMock())
    monkeypatch.setattr(
        "app.automation.flows.scheduled_workflow.tariffs.TariffService", Mock(return_value=service)
    )
    with pytest.raises(type(failure)):
        asyncio.run(refresh_tariffs(None, AsyncMock(), "fixture"))
    service.close.assert_awaited_once()
