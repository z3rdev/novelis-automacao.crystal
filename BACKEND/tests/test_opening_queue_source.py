import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.automation.flows.pendentes.controles.opening_queue import (
    include_opening_queue,
    merge_queue_rows,
    uses_opening_queue,
)
from app.domain.models import RunStartRequest
from app.infrastructure.operations_store import OperationsStore
from app.infrastructure.pending_queue import PendingQueue


def row(number, **fields):
    return {"filial": "10", "serie": "10", "documento": str(number), "cteId": str(number).zfill(44), **fields}


@pytest.mark.parametrize("flow,scope,manual,expected", [
    ("pendentes", "full", "", True),
    ("pendentes", "chamados", "", True),
    ("pendentes", "xml", "", False),
    ("pendentes", "pdf", "", False),
    ("pendentes", "full", "10-10-2881", False),
    ("consulta-pendentes", "full", "", False),
])
def test_queue_is_carried_only_in_automatic_opening_flows(flow, scope, manual, expected):
    request = RunStartRequest(flow=flow, execution_scope=scope, manual_ctes=manual)
    assert uses_opening_queue(request) is expected


def test_fresh_sql_values_win_and_legacy_rows_retain_the_verified_key():
    previous = row(2881, data="2026-11-13", VLR_TOTAL=100)
    current = row(2881, data="2026-11-14", VLR_TOTAL=200)
    assert merge_queue_rows([current], [previous]) == [current]
    legacy = {**current, "cteId": ""}
    assert merge_queue_rows([legacy], [previous]) == [{**legacy, "cteId": previous["cteId"]}]
    assert previous["VLR_TOTAL"] == 100


def test_empty_current_day_keeps_older_pending_until_ticket_confirmation(tmp_path):
    store = OperationsStore(tmp_path / "shared.sqlite")
    store.initialize()
    queue = PendingQueue(store)
    queue.ingest({"rows": [row(2881)], "generatedAt": "2026-11-13T12:00:00Z"}, "confirmed")
    source = tmp_path / "sql-today.json"
    source.write_text('{"rows":[]}', encoding="utf-8")
    settings = SimpleNamespace(novelis_sqlite_path=store.path)
    emit = AsyncMock()
    request = RunStartRequest(flow="pendentes", dry_run=False)
    try:
        output = asyncio.run(include_opening_queue(settings, source, request, emit, "fixture"))
        payload = json.loads(output.read_text(encoding="utf-8"))
        assert payload["rows"] == [row(2881)]
        assert payload["queueEligible"] is False
        assert json.loads(source.read_text(encoding="utf-8")) == {"rows": []}
        assert emit.await_args.kwargs["payload"]["carried"] == 1
        queue.close([row(2881)["cteId"]])
        assert asyncio.run(include_opening_queue(settings, source, request, emit, "later")) == source
    finally:
        store.close()


@pytest.mark.parametrize("name", ["start-hub-preview.ps1", "start-hub-preview-fast.ps1"])
def test_interactive_preview_enables_background_services(name):
    script = (Path(__file__).resolve().parents[2] / "scripts" / name).read_text(encoding="utf-8-sig")
    assert "$env:NOVELIS_BACKEND_READINESS = '0'" in script
    assert "$env:NOVELIS_BACKEND_READINESS = '1'" not in script
