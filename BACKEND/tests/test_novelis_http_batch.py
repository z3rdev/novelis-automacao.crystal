import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from openpyxl import Workbook

from app.automation.cancellation import RunCancellation, cancellation_scope
from app.automation.flows.pendentes.steps.pendentes import PendentesFlow
from app.domain.models import RunStartRequest
from app.domain.run_state import RunState
from app.infrastructure.event_bus import EventBus
from app.infrastructure.operations_store import OperationsStore
from app.services.automation_service import AutomationService
from app.services.novelis_chamado_http.session import HttpChamadosSession
from app.services.novelis_chamado_http.submissions import Submissions

FORM = """<form id="form" action="/portal/chamado" method="POST">
<input type="hidden" name="unique_number" value="nonce">
<input type="hidden" name="id"><input type="hidden" name="button">
<select name="tipo_chamado_id"><option value="0;36">AF.001 - Auditoria de Frete</option></select>
<input name="titulo" required><textarea name="mensagem"></textarea>
<button id="salvar" name="salvar" value="Abrir Chamado"></button></form>"""
FRAGMENT = """<select name="empresa_relacionada"><option value="1" selected>Empresa</option></select>
<input type="file" name="arquivo[0]" class="required-file" data-allowed-file-extensions="pdf">
<input type="file" name="arquivo[1]" class="required-file" data-allowed-file-extensions="xml">
<input type="file" name="arquivo[2]" data-allowed-file-extensions="zip">"""


def plan_fixture(tmp_path, count=2, prechecked=True):
    rows, checked = [], []
    for doc in range(1559, 1559 + count):
        cte, key = f"8-10-{doc}", str(doc).zfill(44)
        row = {
            "filial": "8",
            "serie": "10",
            "documento": str(doc),
            "cteId": key,
            "data": "2026-11-14",
            "ton": "30",
            "idTarifario": "641334",
            "__novelis": {"prechecked": prechecked, "alreadyExists": False},
        }
        pdf, xml = tmp_path / f"CTE_{cte}.pdf", tmp_path / f"CTE_{cte}.xml"
        pdf.write_bytes(b"%PDF-test fixture")
        xml.write_text(
            f'<cteProc xmlns="http://www.portalfiscal.inf.br/cte"><CTe><infCte Id="CTe{key}"><ide><serie>10</serie><nCT>{doc}</nCT></ide></infCte></CTe></cteProc>'
        )
        rows.append(row)
        checked.append(
            {
                "cte": cte,
                "row": row,
                "evidence": {"pdfFile": str(pdf), "xmlFile": str(xml), "comprovanteOk": True},
            }
        )
    plan = {"rows": rows, "checked": checked, "prontosChamado": [item["cte"] for item in checked]}
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan))
    return plan, path


class Portal:
    def __init__(self, rows, fail=None):
        self.calls, self.saved = [], {}
        self.rows, self.fail = rows, fail

    def handle(self, request):
        self.calls.append(request)
        path = request.url.path
        if path == "/login":
            return (
                httpx.Response(302, headers={"location": "/portal"})
                if request.method == "POST"
                else httpx.Response(200, headers={"set-cookie": "XSRF-TOKEN=fixture; Path=/"})
            )
        if path == "/portal/chamado/":
            return httpx.Response(200, text=FORM)
        if path == "/ajax/chamado":
            return httpx.Response(200, text=FRAGMENT)
        if path == "/portal/chamado":
            cte = next(value for value in self.rows if value.encode() in request.content)
            if cte == self.fail:
                return httpx.Response(500)
            number = "20261114" + cte.split("-")[-1].zfill(6)
            self.saved[number] = cte
            return httpx.Response(200, json={"redirect": f"/portal/chamado/{number}"})
        if path.startswith("/portal/chamado/"):
            number = path.rsplit("/", 1)[-1]
            cte = self.saved[number]
            return httpx.Response(
                200,
                text=f'<h2>Resumo do chamado {number}</h2><p>CT-e {cte}</p><a href="/files/1_ctrc-{cte}_2.pdf">PDF</a><a href="/files/1_cte-{cte}_2.xml">XML</a><a href="/files/1_tarifa-641334_2.zip">ZIP</a>',
            )
        if path == "/custom/relatorio_cte_xml":
            return httpx.Response(
                200, text='<form id="form"><input name="de"><input name="ate"></form>'
            )
        if path == "/custom/relatorio_cte_xml_excel":
            book = Workbook()
            book.active.append(["ID", "SERIE", "NCT", "CHAMADO"])
            for number, cte in self.saved.items():
                book.active.append([self.rows[cte]["cteId"], 10, cte.split("-")[-1], number])
            stream = BytesIO()
            book.save(stream)
            return httpx.Response(200, content=stream.getvalue())
        raise AssertionError(f"Unexpected endpoint {path}")


def run_batch(tmp_path, monkeypatch, *, count=2, prechecked=True, fail=None):
    plan, path = plan_fixture(tmp_path, count, prechecked)
    portal = Portal({item["cte"]: item["row"] for item in plan["checked"]}, fail)
    cfg = {
        "user": "fixture",
        "pass": "fixture",
        "chamadosLogFile": str(tmp_path / "processed.json"),
    }
    emit, browser = AsyncMock(), AsyncMock()
    flow = PendentesFlow(SimpleNamespace(backend_root=tmp_path / "BACKEND"), None, None, emit)
    monkeypatch.setattr("app.services.novelis_chamado_http.session.current_catalog", lambda _: None)
    monkeypatch.setattr(
        "app.automation.flows.novelis_chamados.steps.chamado_batch.HttpChamadosSession",
        lambda *args: HttpChamadosSession(*args, transport=httpx.MockTransport(portal.handle)),
    )
    asyncio.run(
        flow._run_chamados(
            browser,
            cfg,
            plan,
            RunStartRequest(dry_run=False),
            "batch",
            {"stopOnError": False},
            path,
        )
    )
    return portal, plan, emit, browser


def test_full_flow_uses_one_http_login_for_multiple_tickets_and_never_uses_browser(
    tmp_path, monkeypatch
):
    portal, plan, emit, browser = run_batch(tmp_path, monkeypatch)
    assert len(portal.saved) == 2 and not plan.get("errors")
    assert browser.mock_calls == []
    assert sum(call.url.path == "/login" and call.method == "POST" for call in portal.calls) == 1
    assert sum(call.url.path == "/portal/chamado" for call in portal.calls) == 2
    assert all("relatorio_cte_xml" not in call.url.path for call in portal.calls)
    results = [
        call.kwargs["payload"]
        for call in emit.await_args_list
        if call.kwargs["kind"] == "novelis.save"
    ]
    assert len(results) == 2 and all(item["attachments_visible"] for item in results)


def test_uncached_report_and_all_tickets_share_the_same_http_session(tmp_path, monkeypatch):
    portal, _, _, _ = run_batch(tmp_path, monkeypatch, prechecked=False)
    assert len(portal.saved) == 2
    assert sum(call.url.path == "/login" and call.method == "POST" for call in portal.calls) == 1
    assert sum(call.url.path == "/custom/relatorio_cte_xml_excel" for call in portal.calls) == 1


def test_partial_failure_preserves_confirmed_tickets_and_continues_batch(tmp_path, monkeypatch):
    portal, plan, emit, _ = run_batch(tmp_path, monkeypatch, count=3, fail="8-10-1560")
    assert len(portal.saved) == 2 and len(plan["errors"]) == 1
    assert plan["errors"][0]["cte"] == "8-10-1560"
    assert sum(call.kwargs["kind"] == "novelis.save" for call in emit.await_args_list) == 2
    assert sum(call.url.path == "/portal/chamado" for call in portal.calls) == 3


def test_failed_authentication_is_not_repeated_for_every_cte(tmp_path, monkeypatch):
    original = Portal.handle

    def denied(self, request):
        if request.url.path == "/login" and request.method == "POST":
            self.calls.append(request)
            return httpx.Response(401)
        return original(self, request)

    monkeypatch.setattr(Portal, "handle", denied)
    portal, plan, _, _ = run_batch(tmp_path, monkeypatch)
    assert not portal.saved and len(plan["errors"]) == 2
    assert sum(call.url.path == "/login" and call.method == "POST" for call in portal.calls) == 1


def test_shared_submission_claim_is_atomic_and_confirmed_state_cannot_regress(tmp_path):
    store = OperationsStore(tmp_path / "shared.sqlite")
    store.initialize()
    config = {"chamadoSubmissionDb": str(store.path)}
    row = {"filial": "8", "serie": "10", "documento": "1559", "cteId": "1" * 44}
    claims = [Submissions(tmp_path, config) for _ in range(6)]
    with ThreadPoolExecutor(max_workers=6) as executor:
        values = list(executor.map(lambda claim: claim.reserve(row, "batch"), claims))
    assert sum(value is None for value in values) == 1
    claims[0].finish(row, {"status": "confirmed", "number": "20261114001559"})
    claims[1].finish(row, {"status": "indeterminate"})
    assert claims[2].reserve(row, "other")["status"] == "confirmed"


def test_normal_full_run_entry_opens_the_whole_batch_over_http(tmp_path, monkeypatch):
    plan, path = plan_fixture(tmp_path)
    plan.update(faltandoPdf=[], faltandoXml=[], faltandoComprovante=[], prontosComprovante=[])
    portal = Portal({item["cte"]: item["row"] for item in plan["checked"]})
    cfg = {
        "user": "fixture",
        "pass": "fixture",
        "chamadosLogFile": str(tmp_path / "processed.json"),
        "relatorioCteXmlTransport": "auto",
    }
    config = SimpleNamespace(
        pendentes=lambda: {"sourceJson": str(path), "outputFile": str(path)},
        rodopar_pdf=dict,
        xml_sefaz=dict,
        comprovante_local=dict,
        chamado_novelis=lambda: cfg,
        consulta_db=dict,
    )
    settings = SimpleNamespace(backend_root=tmp_path / "BACKEND", consulta_browser_headless=False)
    report = AsyncMock(return_value=path)
    monkeypatch.setattr(PendentesFlow, "_refresh_sql_source", AsyncMock(return_value=None))
    refresh = AsyncMock(return_value=plan)
    monkeypatch.setattr(PendentesFlow, "_refresh_plan", refresh)
    monkeypatch.setattr(PendentesFlow, "_refresh_novelis_relatorio", report)
    monkeypatch.setattr(
        PendentesFlow, "_refresh_novelis_relatorio_final", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        "app.automation.flows.pendentes.steps.pendentes.select_pdf_runner", lambda _: AsyncMock()
    )
    monkeypatch.setattr("app.services.novelis_chamado_http.session.current_catalog", lambda _: None)
    monkeypatch.setattr(
        "app.automation.flows.novelis_chamados.steps.chamado_batch.HttpChamadosSession",
        lambda *args: HttpChamadosSession(*args, transport=httpx.MockTransport(portal.handle)),
    )

    async def exercise():
        bus, state, browser = EventBus(), RunState(), AsyncMock()
        service = AutomationService(settings, config, None, bus, state, browser)
        await service.start(RunStartRequest(flow="pendentes", dry_run=False))
        await service._task
        assert (await state.get()).status == "completed"
        assert len(portal.saved) == 2
        assert sum(event.kind == "novelis.save" for event in await bus.history()) == 2
        assert [call[0] for call in browser.mock_calls if not call[0].startswith("__")] == ["close"]
        assert report.await_args.args[2]["relatorioCteXmlTransport"] == "http"
        assert refresh.await_count == 2
        assert refresh.await_args_list[0].kwargs == {"check_files": False}

    asyncio.run(exercise())


@pytest.mark.parametrize("when", ["before", "after"])
def test_cancellation_keeps_the_submission_state_and_confirmed_report_events(
    tmp_path, monkeypatch, when
):
    plan, _ = plan_fixture(tmp_path, count=1)
    row = plan["rows"][0]
    cfg = {"user": "fixture", "pass": "fixture"}
    portal = Portal({item["cte"]: item["row"] for item in plan["checked"]})
    monkeypatch.setattr("app.services.novelis_chamado_http.session.current_catalog", lambda _: None)

    async def exercise():
        cancellation = RunCancellation()
        emitted = []

        async def emit(message, **kwargs):
            emitted.append(kwargs)
            if when == "before" and kwargs["kind"] == "novelis.http.submit":
                cancellation.request_cancel()

        session = HttpChamadosSession(
            tmp_path, cfg, emit, "cancel", transport=httpx.MockTransport(portal.handle)
        )
        remember = session._remember

        def cancel_after_confirmation(*args):
            cancellation.request_cancel()
            return remember(*args)

        if when == "after":
            monkeypatch.setattr(session, "_remember", cancel_after_confirmation)
        with cancellation_scope(cancellation):
            with pytest.raises(asyncio.CancelledError):
                async with session:
                    await session.open(row, {**cfg, "evidence": plan["checked"][0]["evidence"]})
            await cancellation.drain()
        journal = Submissions(tmp_path, cfg)
        previous = journal.reserve(row, "new-run")
        if when == "before":
            assert previous is None and not portal.saved
        else:
            assert previous["status"] == "confirmed" and len(portal.saved) == 1
            assert sum(event["kind"] == "novelis.save" for event in emitted) == 1

    asyncio.run(exercise())
