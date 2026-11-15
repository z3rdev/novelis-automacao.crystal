import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.infrastructure.operations_store import OperationsStore
from app.infrastructure.pending_queue import PendingQueue
from app.services.pending_queue import PendingQueueService, eligible_plan


def row(number, key=None, **fields):
    return {"filial": "2", "serie": "10", "documento": str(number), "cteId": key or str(number).zfill(44), **fields}


def plan(rows, timestamp="2026-11-14T12:00:00Z"):
    return {"generatedAt": timestamp, "sourceFile": "novelis-filtered.json", "sheetName": "JSON", "total":len(rows), "consultados":len(rows),
            "faltandoPdf":[], "faltandoXml":[], "faltandoComprovante":[], "prontosComprovante":[], "prontosChamado":[],
            "checked": [{"row": item} for item in rows]}


@pytest.fixture
def queue(tmp_path):
    store = OperationsStore(tmp_path / "shared.sqlite")
    store.initialize()
    yield PendingQueue(store)
    store.close()


def test_partial_current_day_and_empty_queries_do_not_erase_older_unopened_ctes(queue):
    queue.ingest(plan([row(10)], "2026-11-10T12:00:00Z"), "pc1")
    queue.ingest(plan([row(11)]), "pc1")
    queue.ingest(plan([], "2026-11-14T13:00:00Z"), "pc1")
    assert {value["documento"] for value in queue.rows()} == {"10", "11"}
    other_store = OperationsStore(queue.store.path, machine_id="another-pc")
    other_store.initialize()
    other = PendingQueue(other_store)
    other.ingest(plan([row(12)]), "pc2")
    assert len(queue.rows()) == len(other.rows()) == 3
    other_store.close()


def test_stale_source_cannot_overwrite_newer_data_and_opened_items_cannot_reappear(queue):
    queue.ingest(plan([row(10, data="2026-11-14", VLR_TOTAL=150)]), "pc1")
    queue.ingest(plan([row(10, data="2026-11-10", VLR_TOTAL=100)], "2026-11-10T12:00:00Z"), "old")
    assert queue.rows()[0]["VLR_TOTAL"] == 150
    queue.close([row(10)["cteId"]])
    queue.ingest(plan([row(10)], "2026-11-15T12:00:00Z"), "another-source")
    assert not queue.rows()


def test_legacy_row_without_key_is_replaced_by_enriched_row_without_duplicates(queue):
    queue.ingest(plan([row(10,"invalid")]),"legacy")
    queue.ingest(plan([row(10)]),"enriched")
    queue.ingest(plan([row(10,"invalid")]),"another-legacy")
    assert len(queue.rows())==1 and queue.rows()[0]["cteId"]==row(10)["cteId"]


def test_only_existing_ticket_removes_item_preserving_reused_number_and_other_branch():
    old, current = row(10, "1" * 44), row(10, "2" * 44)
    assert PendingQueueService.unopened([current], [{**old, "chamado": "12345"}]) == [current]
    assert PendingQueueService.unopened([current], [{**current, "chamado": "12345"}]) == []
    without_key = row(10, "invalid")
    assert PendingQueueService.unopened([without_key], [{**row(10, "invalid"), "filial": "8", "chamado": "12345"}]) == [without_key]
    assert PendingQueueService.unopened([current], [{**current, "chamado": None, "andamento": "na_fila"}]) == [current]


def test_manual_xml_pdf_plan_and_unverified_sql_are_not_imported_as_the_opening_queue():
    assert eligible_plan(plan([row(10)]))
    assert not eligible_plan(plan([row(10)]), SimpleNamespace(manual_ctes="2-10-10"))
    assert not eligible_plan({"checked": [{"row": {**row(10), "status": "SQL_ULTIMOS_5_DIAS"}}]})
    assert not eligible_plan({"rows": [{**row(10), "status": "SQL_ULTIMOS_5_DIAS"}]})
    assert not eligible_plan({**plan([row(10)]), "queueEligible": False})


def test_service_does_not_let_a_manual_plan_replace_queue_and_reads_real_document_evidence(queue,tmp_path):
    from test_hub_api import FakeConfig
    config = FakeConfig()
    config.values["pdf"] = {"downloadTargetDir": str(tmp_path / "pdfs")}
    queue.ingest(plan([row(10, data="2026-11-10", VLR_TOTAL=150.25)]), "confirmed")
    root = tmp_path / "BACKEND"
    root.mkdir()
    settings = SimpleNamespace(backend_root=root)
    service = PendingQueueService(settings,config,queue.store,SimpleNamespace(repository=SimpleNamespace(enabled=False)))
    queue.store.local_snapshot("pending_plan",{**plan([row(20)]),"queueEligible":False})
    first = service.load()
    assert len(first)==1 and first[0]["id"]=="2-10-10" and first[0]["pdf"]=="faltando"
    assert first[0]["emissao"]=="2026-11-10" and first[0]["valor"]==150.25
    target = tmp_path / "pdfs/cte-10/CTE_2-10-10.pdf"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"%PDF-test")
    assert service.load()[0]["pdf"]=="disponivel"
    target.unlink()
    assert service.load()[0]["pdf"]=="faltando"


def test_confirmed_plan_is_recorded_by_the_flow_without_any_frontend_polling(queue,tmp_path,monkeypatch):
    from app.automation.flows.pendentes.steps.pendentes import PendentesFlow
    from app.domain.models import RunStartRequest
    value=plan([row(10)])
    settings=SimpleNamespace(backend_root=tmp_path/"BACKEND",novelis_sqlite_path=queue.store.path)
    config=SimpleNamespace(chamado_novelis=lambda:{})
    monkeypatch.setattr("app.automation.flows.pendentes.steps.pendentes.PendentesPlanBuilder.build",AsyncMock(return_value=value))
    flow=PendentesFlow(settings,config,None,AsyncMock())
    monkeypatch.setattr(flow,"_write_plan",lambda *args:None)
    asyncio.run(flow._refresh_plan({}, {}, {}, {}, RunStartRequest(), "fixture"))
    assert len(queue.rows())==1
