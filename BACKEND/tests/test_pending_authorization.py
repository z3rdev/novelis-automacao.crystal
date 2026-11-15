from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.automation.flows.pendentes.controles.opening_queue import merge_queue_rows
from app.automation.flows.pendentes.controles.plan import PendentesPlanBuilder
from app.domain.cte_authorization import authorization_status
from app.infrastructure.operations_store import OperationsStore
from app.infrastructure.pending_queue import PendingQueue
from app.services.pending_authorization import refresh_queue_authorization
from app.services.pending_queue import PendingQueueService


def row(number=26021, **fields):
    return {"filial": "1", "serie": "10", "documento": str(number), "cteId": "", **fields}


def payload(rows, timestamp="2026-11-15T18:00:00Z"):
    return {"generatedAt": timestamp, "rows": rows, "queueEligible": True}


@pytest.fixture
def queue(tmp_path):
    store = OperationsStore(tmp_path / "queue.sqlite")
    store.initialize()
    yield PendingQueue(store)
    store.close()


@pytest.mark.parametrize("fields", [{"CTEAUT": "N"}, {"__sql": {"CTEAUT": " n "}}])
def test_unauthorized_cte_is_excluded_before_scanning_documents(tmp_path, fields):
    builder = PendentesPlanBuilder(tmp_path, AsyncMock())
    approved, denied = row(26022, CTEAUT="S"), row(**fields)
    rows, checked = builder._filter_and_check_rows(
        [denied, approved], approved, {}, {}, {}, {}, check_files=False
    )
    assert rows == [approved]
    assert [item["cte"] for item in checked] == ["1-10-26022"]


def test_existing_legacy_queue_is_reconciled_and_old_cache_cannot_restore_it(queue, monkeypatch):
    legacy = row()
    queue.ingest(payload([legacy]), "old-pc")
    lookup = Mock(return_value=SimpleNamespace(rows=[{**legacy, "CTEAUT": "N"}]))
    monkeypatch.setattr("app.services.pending_authorization.fetch_rows_by_documents", lookup)
    assert refresh_queue_authorization(queue, {"enabled": True}, queue.rows()) == []
    lookup.assert_called_once()
    queue.ingest(payload([legacy], "2099-11-16T18:00:00Z"), "later-cache")
    assert queue.rows() == []


def test_cte_can_enter_again_after_fresh_authorization(queue):
    denied = row(CTEAUT="N")
    queue.ingest(payload([denied]), "rodopar")
    assert queue.rows() == []
    approved = row(CTEAUT="S", cteId="1" * 44)
    queue.ingest(payload([approved], "2026-11-15T19:00:00Z"), "rodopar")
    assert queue.rows() == [approved]
    queue.ingest(payload([denied], "2026-11-15T18:30:00Z"), "stale-pc")
    assert queue.rows() == [approved]


def test_fresh_denial_excludes_previously_keyed_document(queue):
    queue.ingest(payload([row(CTEAUT="S", cteId="1" * 44)]), "rodopar")
    queue.ingest(payload([row(CTEAUT="N")], "2026-11-15T19:00:00Z"), "rodopar")
    assert queue.rows() == []


def test_fresh_sql_denial_removes_carried_queue_item():
    assert merge_queue_rows([row(CTEAUT="N")], [row(CTEAUT="S")]) == []
    assert merge_queue_rows([], [row(__sql={"CTEAUT": "N"})]) == []


def test_current_list_ignores_unauthorized_sql_source_without_importing_unverified_rows(
    queue, tmp_path
):
    import json
    from test_hub_api import FakeConfig

    queue.ingest(payload([row()]), "old-pc")
    sources = tmp_path / "captures/pendentes"
    sources.mkdir(parents=True)
    (sources / "sql-ultimos-5-dias.json").write_text(
        json.dumps(
            {
                "generatedAt": "2026-11-15T19:00:00Z",
                "queueEligible": False,
                "rows": [row(CTEAUT="N"), row(26022, CTEAUT="S", status="SQL_ULTIMOS_5_DIAS")],
            }
        )
    )
    service = PendingQueueService(
        SimpleNamespace(backend_root=tmp_path / "BACKEND"),
        FakeConfig(),
        queue.store,
        SimpleNamespace(repository=SimpleNamespace(enabled=False)),
    )
    assert service.load() == []
    assert queue.rows() == []


def test_unknown_authorization_remains_distinct_from_explicit_denial():
    assert authorization_status(row()) == ""
    assert authorization_status(row(CTEAUT="S", __sql={"CTEAUT": "N"})) == "S"
