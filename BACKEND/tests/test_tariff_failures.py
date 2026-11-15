import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from test_workflow_tariffs import Catalog, request, runner

from app.automation.flows.scheduled_workflow.runner import ScheduledWorkflowRunner
from app.automation.flows.scheduled_workflow.tariffs import refresh_tariffs
from app.infrastructure.chamados_postgres import CommunicationUnavailable
from app.services.tariffs.errors import TariffRefreshError, failure_code
from app.services.tariffs.service import TariffService


def test_driver_timeout_retains_safe_cause_and_preserves_the_previous_catalog():
    class DriverTimeout(Exception):
        sqlstate = "57014"

    class Database(Catalog):
        def __init__(self):
            super().__init__()
            self.total = 10027

        def save(self, *args):
            try:
                raise DriverTimeout("private SQL, connection and credential fixture")
            except DriverTimeout:
                raise CommunicationUnavailable("private driver message") from None

        def fail(self, lease, message, **diagnostic):
            super().fail(lease, message)
            self.diagnostic = diagnostic

        def sync_status(self):
            diagnostic = getattr(self, "diagnostic", {})
            return {**super().sync_status(), "stage": diagnostic.get("stage"),
                    "error_code": diagnostic.get("code")}

    async def exercise():
        database = Database()
        collector = AsyncMock(return_value=([], {}))
        service = TariffService(None, database, collector)
        with pytest.raises(TariffRefreshError) as result:
            await service.refresh_and_wait()
        assert database.total == 10027 and database.state == "failed"
        assert database.diagnostic == {"stage": "gravacao", "code": "57014"}
        assert result.value.code == "57014" and result.value.stage == "gravacao"
        assert "tempo limite" in database.message and "57014" in database.message
        assert "private" not in database.message + str(result.value)
        await service.close()

    asyncio.run(exercise())


@pytest.mark.parametrize("code", ["57014", "55P03", "23505"])
def test_workflow_event_identifies_database_failure_without_raw_details(code, monkeypatch):
    failure = TariffRefreshError({"stage": "gravacao", "error_code": code})
    service = SimpleNamespace(refresh_and_wait=AsyncMock(side_effect=failure), close=AsyncMock())
    monkeypatch.setattr(
        "app.automation.flows.scheduled_workflow.tariffs.TariffService", lambda config: service
    )
    emit = AsyncMock()
    with pytest.raises(TariffRefreshError):
        asyncio.run(refresh_tariffs(None, emit, "fixture"))
    event = emit.await_args_list[-1]
    assert event.kwargs["kind"] == "tariffs.refresh_failed"
    assert event.kwargs["payload"] == {"stage": "gravacao", "error_code": code}
    service.close.assert_awaited_once()


def test_workflow_failed_node_explains_the_tariff_failure(tmp_path, monkeypatch):
    failure = TariffRefreshError({"stage": "gravacao", "error_code": "57014"})
    emit = AsyncMock()
    workflow = runner(tmp_path, emit)
    monkeypatch.setattr(ScheduledWorkflowRunner, "tariffs", AsyncMock(side_effect=failure))
    with pytest.raises(TariffRefreshError):
        asyncio.run(workflow.run(None, request("tariffs"), "fixture"))
    event = emit.await_args_list[-1]
    assert event.kwargs["kind"] == "workflow.node.failed"
    assert event.kwargs["payload"]["sync_stage"] == "gravacao"
    assert event.kwargs["payload"]["error_code"] == "57014"
    assert "tempo limite" in event.args[0]


def test_unknown_driver_details_and_codes_do_not_escape_to_the_interface():
    failure = RuntimeError("private fixture")
    failure.sqlstate = "password=private"
    assert failure_code(failure, "gravacao") == "database"
    failure.__context__ = failure
    assert failure_code(failure, "gravacao") == "database"
    value = TariffRefreshError({"stage": "gravacao", "error_code": "password=private"})
    assert "private" not in str(value) and value.code == "database"
    interrupted = TariffRefreshError({"state": "interrupted", "stage": "gravacao"})
    assert "interrompida" in str(interrupted) and interrupted.code == "interrupted"
