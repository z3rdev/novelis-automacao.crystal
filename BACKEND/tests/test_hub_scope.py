from app.automation.flows.pendentes.controles.execution_scope import scoped_config
from app.automation.flows.pendentes.controles.guards import should_block_unfiltered_execution
from app.domain.models import RunStartRequest
from app.services.hub_views import job_views, run_view


def test_pdf_scope_excludes_xml_comprovantes_and_business_calls():
    original = {"refreshNovelisRelatorio": True}
    result = scoped_config(original, RunStartRequest(execution_scope="pdf"))
    assert all(result[key] for key in ("skipXml", "skipComprovantes", "skipNovelis"))
    assert result["refreshNovelisRelatorio"] is False
    assert result["requireNovelisFilterBeforeExecution"] is False
    assert original == {"refreshNovelisRelatorio": True}


def test_pdf_only_accepts_sql_documents_without_requiring_the_disabled_portal_filter():
    original = {"requireNovelisFilterBeforeExecution": True, "refreshNovelisRelatorio": True}
    plan = {"checked": [{"cte": "2-10-17419"}],
            "rows": [{"status": "SQL_ULTIMOS_5_DIAS"}], "sourceFile": "sql.json"}
    config = scoped_config(original, RunStartRequest(execution_scope="pdf"))
    assert should_block_unfiltered_execution(config, plan, None, None, None, None) is False
    full = scoped_config(original, RunStartRequest(execution_scope="full"))
    assert should_block_unfiltered_execution(full, plan, None, None, None, None) is True


def test_document_scope_keeps_document_stages_but_excludes_calls():
    result = scoped_config({}, RunStartRequest(execution_scope="documents"))
    assert result["skipNovelis"] is True
    assert not result.get("skipXml")


def test_hub_does_not_mark_current_document_as_completed():
    snapshot = {"id": "one", "flow": "pendentes", "status": "running"}
    result = run_view(snapshot, [{"kind": "crystal_pdf.progress", "payload": {"current": 2, "total": 4}}])
    assert result["processados"] == 1 and result["total"] == 4
    assert len(result["stages"]) == 5


def test_query_only_does_not_claim_documents_and_chamados_were_generated():
    result = run_view({"id": "one", "flow": "consulta-pendentes", "status": "completed"}, [])
    assert result["flow"] == "consulta"
    assert result["stages"][0]["state"] == "concluida"
    assert all(stage["state"] == "ignorada" for stage in result["stages"][1:])


def test_pdf_stage_can_complete_while_xml_is_still_running():
    result = run_view({"id": "one", "flow": "pendentes", "status": "running"}, [
        {"kind": "crystal_pdf.progress", "payload": {"current": 1, "total": 1}},
        {"kind": "crystal_pdf.saved", "payload": {}},
        {"kind": "xml_sefaz.progress", "payload": {"current": 1, "total": 1}},
    ])
    assert result["stages"][1]["state"] == "concluida"
    assert result["stages"][2]["state"] == "executando"


def test_cancelled_query_never_keeps_a_stage_running():
    result = run_view({"id": "one", "flow": "consulta-pendentes", "status": "cancelled"}, [
        {"kind": "pendentes.sql_loaded", "payload": {"total": 442}},
        {"kind": "run.cancelled", "payload": {}},
    ])
    assert result["stages"][0]["state"] == "cancelada"
    assert all(stage["state"] != "executando" for stage in result["stages"])
    result = run_view({"id": "one", "flow": "pendentes", "status": "stopping"}, [
        {"kind": "crystal_pdf.progress", "payload": {"current": 1, "total": 4}},
    ])
    assert result["stages"][1]["state"] == "parando"


def test_interrupted_pdf_job_is_not_left_running():
    jobs = job_views([
        {"kind": "crystal_pdf.progress", "run_id": "one", "payload": {"cte": "2-10-10402"}},
        {"kind": "run.cancelled", "run_id": "one", "payload": {}},
    ])
    assert jobs[0]["state"] == "cancelada"


def test_existing_pdf_and_xml_stages_remain_available_after_run_is_cancelled():
    result = run_view({"id": "one", "flow": "pendentes", "status": "cancelled"}, [
        {"kind": "crystal_pdf.skip", "payload": {"available": 14}, "message": "14 PDFs ja disponiveis"},
        {"kind": "pendentes.xml_skip", "payload": {"available": 14}, "message": "14 XMLs ja disponiveis"},
    ])
    for stage in result["stages"][1:3]:
        assert stage["state"] == "concluida" and stage["reaproveitados"] == 14
        assert "disponiveis" in stage["detalhe"]
