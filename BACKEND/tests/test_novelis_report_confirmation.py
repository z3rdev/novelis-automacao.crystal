import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from app.automation.flows.novelis_chamados.steps.novelis import NovelisFlow


@pytest.mark.parametrize("row,expected", [
    ({"filial": 8, "serie": 10, "documento": 1559}, "8-10-1559"),
    ({"numeroCte": "8-10-1559"}, "8-10-1559"),
    ({"cte": "8-10-1559"}, "8-10-1559"), ({}, ""),
])
def test_overlay_derives_cte_from_the_current_row_without_a_global_variable(tmp_path, row, expected):
    assert NovelisFlow(tmp_path, AsyncMock())._overlay_state(row) == {"cte": expected}


def test_real_chamado_preparation_handles_existing_ticket_without_opening_a_new_one(tmp_path, monkeypatch):
    emit = AsyncMock()
    flow = NovelisFlow(tmp_path, emit)
    row = {"filial": 8, "serie": 10, "documento": 1559}
    flow._resolve_tarifario_row = lambda config: row
    flow._find_existing_chamado = lambda config, value: {"chamadoNumero": "202611140001"}
    flow._mark_processed = Mock()
    flow.ensure_portal_authenticated = AsyncMock()
    monkeypatch.setattr("app.automation.flows.novelis_chamados.steps.novelis.update_novelis_overlay", AsyncMock())
    monkeypatch.setattr("app.automation.flows.novelis_chamados.steps.novelis.wait_if_novelis_paused", AsyncMock())
    asyncio.run(flow.run_chamado_flow(AsyncMock(), {}, "fixture"))
    event = next(call for call in emit.await_args_list if call.kwargs.get("kind") == "novelis.chamado_exists")
    assert event.kwargs["payload"]["ticket"]["cte"] == "8-10-1559"
    flow.ensure_portal_authenticated.assert_not_awaited()
    flow._mark_processed.assert_called_once_with({}, row, "ja_existia", "202611140001")
