import asyncio
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.automation.flows.novelis_chamados.steps.chamado_http import run_http_test
from app.domain.models import RunStartRequest
from app.domain.run_state import RunState
from app.infrastructure.event_bus import EventBus
from app.services.automation_service import AutomationService
from app.services.execution_reports.models import entries
from app.services.novelis_chamado_http import ChamadoHttpError, runner


def test_app_dispatches_http_flow_with_no_browser(tmp_path, monkeypatch):
    from app.automation.flows.legacy_coordinator.controles.coordinator import LegacyCoordinator

    handler = AsyncMock(return_value={"status": "prepared"})
    monkeypatch.setattr(
        "app.automation.flows.novelis_chamados.steps.chamado_http.run_http_test", handler
    )

    async def execute():
        state, bus = RunState(), EventBus()
        browser = Mock()
        settings = SimpleNamespace(
            backend_root=tmp_path / "BACKEND", consulta_browser_headless=False
        )
        service = AutomationService(settings, Mock(), Mock(), bus, state, browser)
        await service.start(
            RunStartRequest(flow="chamado-http", dry_run=False, sample_cte="8-10-1559")
        )
        task = service._task
        await task
        assert (await state.get()).status == "completed"
        assert browser.mock_calls == []
        handler.assert_awaited_once()
        coordinator = LegacyCoordinator(settings, Mock(), Mock(), bus)
        await coordinator.run(
            RunStartRequest(flow="chamado-http", sample_cte="8-10-1559"), "r", None
        )
        assert handler.await_count == 2

    asyncio.run(execute())


def test_confirmed_app_result_populates_execution_report(tmp_path, monkeypatch):
    value = {
        "status": "confirmed",
        "number": "20261114999999",
        "attachments_visible": True,
        "catalog_updated": True,
        "ticket": {"cte": "8-10-1559", "numero": "20261114999999"},
    }
    monkeypatch.setattr(
        "app.automation.flows.novelis_chamados.steps.chamado_http.run_ticket_test",
        AsyncMock(return_value=value),
    )
    emit = AsyncMock()
    asyncio.run(
        run_http_test(
            SimpleNamespace(backend_root=tmp_path / "BACKEND"),
            Mock(),
            RunStartRequest(sample_cte="8-10-1559", dry_run=False),
            "r",
            emit,
        )
    )
    events = [
        {"kind": call.kwargs["kind"], "payload": call.kwargs.get("payload", {})}
        for call in emit.await_args_list
    ]
    opened, existing = entries(events)
    assert len(opened) == 1 and opened[0]["numero"] == value["number"] and existing == []


def test_uncertain_app_save_is_failed_and_never_falls_back_to_browser(tmp_path, monkeypatch):
    submit = AsyncMock(
        return_value={"status": "indeterminate", "submitted": True, "save_http": 500}
    )
    monkeypatch.setattr(
        "app.automation.flows.novelis_chamados.steps.chamado_http.run_ticket_test", submit
    )
    with pytest.raises(ChamadoHttpError, match="ainda não confirmou"):
        asyncio.run(
            run_http_test(
                SimpleNamespace(backend_root=tmp_path / "BACKEND"),
                Mock(),
                RunStartRequest(sample_cte="8-10-1559", dry_run=False),
                "r",
                AsyncMock(),
            )
        )
    submit.assert_awaited_once()


def test_cancellation_persists_uncertainty_and_prevents_a_second_save(tmp_path, monkeypatch):
    @asynccontextmanager
    async def authenticated(_cfg):
        yield Mock()

    row = {"filial": "8", "serie": "10", "documento": "1559"}
    monkeypatch.setattr(
        runner, "resolve_inputs", Mock(return_value=(row, {}, {}, "title", "message"))
    )
    monkeypatch.setattr(runner, "existing_ticket", AsyncMock(return_value=""))
    monkeypatch.setattr(runner, "authenticated", authenticated)
    monkeypatch.setattr(runner, "prepare", AsyncMock(return_value=SimpleNamespace(uploads={})))
    submit = AsyncMock(side_effect=asyncio.CancelledError())
    monkeypatch.setattr(runner, "submit_once", submit)
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(runner.run_ticket_test(Mock(), Mock(), "8-10-1559", first, send=True))
    assert (
        json.loads((tmp_path / "submission-8-10-1559.json").read_text())["status"]
        == "indeterminate"
    )
    with pytest.raises(ChamadoHttpError, match="já teve um envio"):
        asyncio.run(runner.run_ticket_test(Mock(), Mock(), "8-10-1559", second, send=True))
    submit.assert_awaited_once()


def test_http_200_without_number_is_reconciled_without_repeating_save(tmp_path, monkeypatch):
    @asynccontextmanager
    async def authenticated(_cfg):
        yield Mock()

    row = {"filial": "8", "serie": "10", "documento": "1559"}
    monkeypatch.setattr(
        runner, "resolve_inputs", Mock(return_value=(row, {}, {}, "title", "message"))
    )
    lookup = AsyncMock(side_effect=["", "20261114999999"])
    monkeypatch.setattr(runner, "existing_ticket", lookup)
    monkeypatch.setattr(runner, "authenticated", authenticated)
    monkeypatch.setattr(runner, "prepare", AsyncMock(return_value=SimpleNamespace(uploads={})))
    submit = AsyncMock(
        return_value={"status": "indeterminate", "submitted": True, "save_http": 200}
    )
    monkeypatch.setattr(runner, "submit_once", submit)
    monkeypatch.setattr(
        runner,
        "verify_ticket",
        AsyncMock(
            return_value={"status": "confirmed", "number": "20261114999999", "submitted": True}
        ),
    )
    monkeypatch.setattr(
        runner,
        "ChamadosCatalog",
        Mock(return_value=SimpleNamespace(repository=SimpleNamespace(enabled=False))),
    )
    output = tmp_path / "test"
    output.mkdir()
    result = asyncio.run(runner.run_ticket_test(Mock(), Mock(), "8-10-1559", output, send=True))
    assert result["status"] == "confirmed" and lookup.await_args.kwargs == {"fresh": True}
    submit.assert_awaited_once()
