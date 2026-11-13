import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.automation.flows.pendentes.controles.plan import PendentesPlanBuilder
from app.automation.flows.pendentes.steps.pendentes import PendentesFlow
from app.config.legacy_config import LegacyConfig
from app.domain.models import RunStartRequest
from app.domain.run_state import RunState
from app.infrastructure.event_bus import EventBus
from app.services.automation_service import AutomationService


def test_missing_consulta_fails_instead_of_producing_successful_empty_plan(tmp_path):
    emit = AsyncMock()
    builder = PendentesPlanBuilder(tmp_path, emit)
    with pytest.raises(RuntimeError, match="Fonte de consulta indisponivel"):
        asyncio.run(builder.build({}, {}, {}, {}, RunStartRequest(), "missing"))
    assert emit.call_args.kwargs["kind"] == "pendentes.consulta_failed"


def test_source_failure_reaches_failed_status_through_normal_run_entry(tmp_path):
    settings = SimpleNamespace(backend_root=tmp_path / "BACKEND", pre_url="about:blank",
                               pre_html5_url="about:blank", pre_step_delay_ms=0,
                               consulta_browser_headless=False)
    legacy = LegacyConfig(settings)
    events = EventBus()
    browser = SimpleNamespace(close=AsyncMock())
    service = AutomationService(settings, legacy, None, events, RunState(), browser)

    async def scenario():
        await service.start(RunStartRequest(flow="consulta-pendentes", dry_run=False))
        await asyncio.wait_for(service._task, timeout=3)
        return await service.current(), await events.history()

    state, history = asyncio.run(scenario())
    assert state.status == "failed"
    assert "Fonte de consulta indisponivel" in state.message
    assert [event.kind for event in history] == [
        "run.started", "pendentes.sql_disabled", "pendentes.consulta_failed",
        "run.failed", "browser.closed",
    ]
    browser.close.assert_awaited_once()


def test_valid_empty_json_remains_a_successful_empty_result(tmp_path):
    (tmp_path / "empty.json").write_text('{"rows": []}', encoding="utf-8")
    builder = PendentesPlanBuilder(tmp_path, AsyncMock())
    plan = asyncio.run(builder.build(
        {"sourceJson": "empty.json"}, {}, {}, {}, RunStartRequest(), "empty"))
    assert plan["total"] == 0
    assert plan["sourceFile"] == str(tmp_path / "empty.json")


def test_explicit_sample_still_runs_without_a_spreadsheet(tmp_path):
    builder = PendentesPlanBuilder(tmp_path, AsyncMock())
    request = RunStartRequest(sample_filial="2", sample_documento="10402")
    plan = asyncio.run(builder.build({}, {}, {}, {}, request, "sample"))
    assert [row["cte"] for row in plan["rows"]] == ["2-10-10402"]


@pytest.mark.parametrize("refresh,enabled", [(False, True), (True, False), (False, False)])
def test_disabled_sql_emits_both_configuration_flags(tmp_path, refresh, enabled):
    emit = AsyncMock()
    flow = PendentesFlow(SimpleNamespace(backend_root=tmp_path / "BACKEND"), None, None, emit)
    assert asyncio.run(flow._refresh_sql_source(
        {"refreshSql": refresh}, {"enabled": enabled}, "disabled")) is None
    assert emit.call_args.kwargs["kind"] == "pendentes.sql_disabled"
    assert emit.call_args.kwargs["payload"] == {"refreshSql": refresh, "enabled": enabled}


def test_sql_failure_and_missing_local_input_cannot_become_empty_success(tmp_path, monkeypatch):
    def fail(*_args):
        raise RuntimeError("Cannot open requested database (4060)")

    monkeypatch.setattr("app.automation.flows.pendentes.steps.pendentes.fetch_last_5_days_rows", fail)
    emit = AsyncMock()
    flow = PendentesFlow(SimpleNamespace(backend_root=tmp_path / "BACKEND"), None, None, emit)

    async def scenario():
        config = {"refreshSql": True, "strictSql": False}
        assert await flow._refresh_sql_source(config, {"enabled": True}, "sql-failure") is None
        return await PendentesPlanBuilder(tmp_path, emit).build(
            config, {}, {}, {}, RunStartRequest(), "sql-failure")

    with pytest.raises(RuntimeError, match="Fonte de consulta indisponivel"):
        asyncio.run(scenario())
    kinds = [call.kwargs["kind"] for call in emit.call_args_list]
    assert kinds == ["pendentes.sql_refresh", "pendentes.sql_error", "pendentes.consulta_failed"]


def test_available_local_source_remains_supported_after_sql_failure(tmp_path, monkeypatch):
    def fail(*_args):
        raise RuntimeError("SQL unavailable")

    monkeypatch.setattr("app.automation.flows.pendentes.steps.pendentes.fetch_last_5_days_rows", fail)
    (tmp_path / "cached.json").write_text(json.dumps({"rows": []}), encoding="utf-8")
    flow = PendentesFlow(SimpleNamespace(backend_root=tmp_path / "BACKEND"), None, None, AsyncMock())

    async def scenario():
        config = {"refreshSql": True, "sourceJson": "cached.json"}
        assert await flow._refresh_sql_source(config, {"enabled": True}, "fallback") is None
        return await PendentesPlanBuilder(tmp_path, flow.emit).build(
            config, {}, {}, {}, RunStartRequest(), "fallback")

    assert asyncio.run(scenario())["total"] == 0
