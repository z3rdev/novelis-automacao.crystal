import asyncio
from unittest.mock import AsyncMock

from app.domain.models import RunStartRequest
from app.services.hub_views import run_view

SNAPSHOT = {"id": "fixture", "flow": "pendentes", "status": "running", "started_at": None}


def event(kind, payload=None):
    return {"kind": kind, "payload": payload or {}, "message": kind, "level": "info"}


def query_stage(events):
    view = run_view(SNAPSHOT, events)
    return view, next(stage for stage in view["stages"] if stage["id"] == "consulta")


def test_sql_report_and_filesystem_have_distinct_live_sources():
    _, stage = query_stage([event("pendentes.sql_refresh")])
    assert stage["atividade"] == "SQL Server" and stage["state"] == "executando"
    _, stage = query_stage([event("pendentes.manual_sql_refresh")])
    assert stage["atividade"] == "SQL Server" and stage["state"] == "executando"
    _, stage = query_stage(
        [event("pendentes.sql_loaded", {"total": 20}), event("novelis_relatorio.http_download")]
    )
    assert stage["atividade"] == "Relatório Novelis" and stage["state"] == "executando"
    _, stage = query_stage(
        [event("pendentes.sql_loaded", {"total": 20}), event("pendentes.files_check")]
    )
    assert stage["atividade"] == "Arquivos" and stage["state"] == "executando"
    _, stage = query_stage(
        [event("pendentes.sql_loaded", {"total": 20}), event("pendentes.plan", {"total": 0})]
    )
    assert stage["total"] == stage["done"] == 0 and stage["state"] == "concluida"


def test_novelis_session_checks_are_chamado_activity_instead_of_sql_query():
    view, stage = query_stage(
        [event("pendentes.sql_loaded", {"total": 20}), event("novelis.session_reused")]
    )
    assert view["etapaAtual"] == "chamados" and stage["state"] == "concluida"
    view, stage = query_stage([event("novelis.save"), event("novelis_relatorio.http_download")])
    assert view["etapaAtual"] == "consulta" and stage["atividade"] == "Relatório Novelis"


def test_ready_documents_still_emit_explicit_file_check_without_querying_sql(tmp_path, monkeypatch):
    from app.automation.flows.pendentes.controles.plan import PendentesPlanBuilder

    emit = AsyncMock()
    builder = PendentesPlanBuilder(tmp_path, emit)
    row = {"filial": "8", "serie": "10", "documento": "1559"}
    builder._input_rows = AsyncMock(return_value=([row], "existing-source.json", "JSON"))
    builder._filter_and_check_rows = lambda rows, *args: (
        rows,
        [
            {
                "cte": "8-10-1559",
                "row": row,
                "evidence": {"pdfFile": "ready.pdf", "xmlFile": "ready.xml", "comprovanteOk": True},
            }
        ],
    )
    result = asyncio.run(builder.build({}, {}, {}, {}, RunStartRequest(), "fixture"))
    assert not result["faltandoPdf"] and not result["faltandoXml"]
    assert result["prontosChamado"] == ["8-10-1559"]
    notice = next(
        call for call in emit.await_args_list if call.kwargs.get("kind") == "pendentes.files_check"
    )
    assert notice.kwargs["payload"]["querySource"] == "arquivos"
