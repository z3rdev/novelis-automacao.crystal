import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.automation.flows.pendentes.controles.pdf_xml_parallel import PdfXmlParallelRunner
from app.automation.flows.pendentes.controles.plan import PendentesPlanBuilder
from app.automation.flows.pendentes.controles.plan_reuse import filtered_plan
from app.domain.models import RunStartRequest


def test_loading_rows_before_portal_filter_does_not_scan_files(tmp_path, monkeypatch):
    row = {"filial": "8", "serie": "10", "documento": "1559", "cteId": "1" * 44}
    source = tmp_path / "source.json"
    source.write_text(json.dumps({"rows": [row]}))

    def no_scan(*_args):
        raise AssertionError("Unexpected filesystem scan before Novelis filtering")

    monkeypatch.setattr("app.automation.flows.pendentes.controles.plan.scan_evidence", no_scan)
    monkeypatch.setattr("app.services.chamados_catalog.current_catalog", lambda _: None)
    emit = AsyncMock()
    value = asyncio.run(
        PendentesPlanBuilder(tmp_path, emit).build(
            {"sourceJson": str(source)}, {}, {}, {}, RunStartRequest(), "rows", check_files=False
        )
    )
    assert len(value["rows"]) == 1 and not value["prontosChamado"]
    assert not any(call.kwargs["kind"] == "pendentes.files_check" for call in emit.await_args_list)


def test_file_plan_uses_indexed_catalog_read_without_bulk_import(tmp_path, monkeypatch):
    rows = [
        {"filial": "8", "serie": "10", "documento": str(doc), "cteId": str(doc).zfill(44)}
        for doc in (1559, 1560)
    ]
    catalog = SimpleNamespace(
        opened_identities=lambda wanted: [
            {**rows[0], "cte": "8-10-1559", "chamado": "20261114000001"}
        ]
    )
    monkeypatch.setattr("app.services.chamados_catalog.current_catalog", lambda _: catalog)
    builder = PendentesPlanBuilder(tmp_path, AsyncMock())
    assert builder._exclude_existing_chamados(rows, {}) == [rows[1]]


def test_final_portal_filter_reuses_evidence_and_filters_totals():
    rows = [
        {"filial": "8", "serie": "10", "documento": str(doc), "cteId": str(doc).zfill(44)}
        for doc in (1559, 1560)
    ]
    evidence = {"pdfFile": "exact.pdf", "xmlFile": "exact.xml"}
    previous = {
        "checked": [
            {"cte": f"8-10-{row['documento']}", "row": row, "evidence": evidence} for row in rows
        ],
        "rows": rows,
        "prontosChamado": ["8-10-1559", "8-10-1560"],
        "prontosComprovante": [],
        "faltandoPdf": [],
        "faltandoXml": [],
        "faltandoComprovante": [],
    }
    final = filtered_plan(previous, {"rows": [rows[1]]}, "filtered.json")
    assert final["total"] == 1 and final["prontosChamado"] == ["8-10-1560"]
    assert final["checked"][0]["evidence"] is evidence
    assert filtered_plan(previous, {"rows": [{**rows[0], "cteId": "9" * 44}]}, "new.json") is None


def test_available_pdf_and_xml_do_not_rebuild_the_file_plan():
    pdf, xml, refresh = AsyncMock(), AsyncMock(), AsyncMock()
    plan = {"faltandoPdf": [], "faltandoXml": []}
    runner = PdfXmlParallelRunner(SimpleNamespace(), AsyncMock(), pdf, xml, refresh)
    result = asyncio.run(runner.run(None, {}, {}, {}, plan, RunStartRequest(), "ready", {}, None))
    assert result is plan
    pdf.assert_awaited_once()
    xml.assert_awaited_once()
    refresh.assert_not_awaited()


def test_report_cache_uses_the_operator_day_across_utc_midnight(tmp_path):
    from app.automation.flows.novelis_relatorio.steps.novelis_relatorio_cte_xml import (
        NovelisRelatorioCteXmlFlow,
    )

    flow = NovelisRelatorioCteXmlFlow(tmp_path, AsyncMock())
    local_now = datetime(2026, 11, 14, 22, 0, tzinfo=timezone(timedelta(hours=-3)))
    assert flow._is_today("2026-11-14T23:30:00+00:00", now=local_now)
    assert not flow._is_today("2026-11-14T00:30:00+00:00", now=local_now)
