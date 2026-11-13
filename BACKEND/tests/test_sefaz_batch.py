import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.automation.flows.pendentes.controles import xml_batch
from app.automation.flows.pendentes.controles.execution_scope import scoped_config
from app.automation.flows.pendentes.controles.plan import PendentesPlanBuilder
from app.domain.models import RunStartRequest
from app.automation.flows.pendentes.steps.pendentes import PendentesFlow
from app.services.cte_xml_files import matching_xml_files, validate_download
from app.services.sefaz_browser_profile import create_profile, remove_profile
from app.services.sefaz_certificate import certificate_rule, select_certificate

KEY = "35260112345678000199570100000231671123456780"


def content(key=KEY, number="23167"):
    return (f'<cteProc xmlns="http://www.portalfiscal.inf.br/cte"><CTe><infCte Id="CTe{key}">'
            f'<ide><serie>10</serie><nCT>{number}</nCT></ide></infCte></CTe></cteProc>')


def test_xml_scope_uses_only_xml_even_when_legacy_flag_was_disabled():
    config = scoped_config({"skipXml": True}, RunStartRequest(execution_scope="xml"))
    assert config["skipPdf"] and config["skipNovelis"] and config["skipComprovantes"]
    assert config["skipXml"] is False
    assert config["refreshNovelisRelatorio"] is False


def test_evidence_rejects_partial_number_other_branch_and_html(tmp_path):
    row = {"filial": 1, "serie": 10, "documento": 23167, "cteId": KEY}
    (tmp_path / "CTE_2-10-23167.xml").write_text(content(key="0" * 44))
    (tmp_path / "CTE_1-10-123167.xml").write_text(content(number="123167"))
    exact = tmp_path / "CTE_1-10-23167.xml"
    exact.write_text("<html>Erro de autenticacao</html>")
    assert matching_xml_files(tmp_path, row) == []
    exact.write_text(content())
    assert matching_xml_files(tmp_path, row) == [exact]
    with pytest.raises(ValueError, match="chave"):
        validate_download(exact, {**row, "cteId": "1" * 44})


def test_explicit_xml_list_is_not_removed_by_chamado_history(tmp_path, monkeypatch):
    rows = [{"filial": "1", "serie": "10", "documento": "23167", "chamado": "SIM", "cteId": KEY}]
    builder = PendentesPlanBuilder(tmp_path, AsyncMock())
    monkeypatch.setattr("app.automation.flows.pendentes.controles.plan.read_processed_ctes",
                        lambda *a: pytest.fail("A lista explicita de XML nao pode ser filtrada pelo historico"))
    _, checked = builder._filter_and_check_rows(rows, None, {}, {}, {}, {}, explicit_xml=True)
    assert [i["cte"] for i in checked] == ["1-10-23167"]


def test_xml_batch_downloads_every_missing_cte_and_skips_existing(monkeypatch, tmp_path):
    emit = AsyncMock()
    download = AsyncMock()
    monkeypatch.setattr(xml_batch, "XmlSefazFlow", lambda *a: SimpleNamespace(run=download))
    ctes = ["2-10-10402", "1-10-23167", "11-10-397"]
    plan = {"checked": [{"cte": cte} for cte in ctes], "faltandoXml": ctes[1:]}
    asyncio.run(xml_batch.run_xml_batch(SimpleNamespace(cwd=tmp_path, emit=emit), None, {}, plan,
        RunStartRequest(execution_scope="xml", manual_ctes="\n".join(ctes)), "batch", {}, tmp_path / "plan.json"))
    assert [c.args[1]["ctes"] for c in download.await_args_list] == ctes[1:]
    assert all(c.args[2].sample_cte == c.args[1]["ctes"] for c in download.await_args_list)
    assert [c.kwargs["payload"]["total"] for c in emit.await_args_list] == [2, 2]


def test_batch_errors_cannot_appear_as_success(monkeypatch, tmp_path):
    monkeypatch.setattr(xml_batch, "XmlSefazFlow", lambda *a: SimpleNamespace(run=AsyncMock(side_effect=RuntimeError("sem chave"))))
    with pytest.raises(RuntimeError, match="XML SEFAZ com pendencias"):
        asyncio.run(xml_batch.run_xml_batch(SimpleNamespace(cwd=tmp_path, emit=AsyncMock()), None, {},
            {"checked": [{"cte": "1-10-23167"}], "faltandoXml": ["1-10-23167"]},
            RunStartRequest(), "batch", {"stopOnError": False}, tmp_path / "plan.json"))


def test_xml_scope_enriches_entire_list_from_sql_and_downloads_without_pdf_or_novelis(monkeypatch, tmp_path):
    rows = [{"filial": str(f), "serie": "10", "documento": str(n),
             "cteId": "3526011325410400017457010" + f"{n:09d}" + "1123456780"}
            for f, n in [(2, 10402), (1, 23167), (11, 397)]]
    ctes = [f"{r['filial']}-10-{r['documento']}" for r in rows]
    monkeypatch.setattr("app.automation.flows.pendentes.controles.manual_input.fetch_rows_by_documents",
                        lambda *a: SimpleNamespace(rows=rows, source={}))
    monkeypatch.setattr("app.automation.flows.pendentes.steps.pendentes.select_pdf_runner",
                        lambda *a: pytest.fail("Somente XML nao deve iniciar Crystal/Rodopar"))
    config = SimpleNamespace(
        pendentes=lambda: {"skipXml": True, "outputFile": str(tmp_path / "plan.json")},
        consulta_db=lambda: {"enabled": True},
        rodopar_pdf=lambda: {},
        xml_sefaz=lambda: {"downloadDir": str(tmp_path / "xmls")},
        comprovante_local=lambda: {}, chamado_novelis=lambda: {},
    )
    called = []

    async def download(browser, cfg, request, run_id):
        row = rows[ctes.index(cfg["ctes"])]
        target = tmp_path / "xmls" / f"CTE_{cfg['ctes']}.xml"
        target.parent.mkdir(exist_ok=True)
        target.write_text(content(row["cteId"], row["documento"]))
        called.append(cfg["ctes"])

    monkeypatch.setattr(xml_batch, "XmlSefazFlow", lambda *a: SimpleNamespace(run=download))
    flow = PendentesFlow(SimpleNamespace(backend_root=tmp_path / "BACKEND"), config, None, AsyncMock())
    result = asyncio.run(flow.run(None, RunStartRequest(flow="pendentes", dry_run=False,
                            execution_scope="xml", manual_ctes="\n".join(ctes)), "xml-batch"))
    assert called == ctes and result["total"] == 3 and result["faltandoXml"] == []


def test_certificate_selects_matriz_rejects_ambiguity_and_uses_disposable_profile(tmp_path):
    matriz = {"subjectCN": "DELLMAR:13254104000174", "issuerCN": "AC SERPRO", "thumbprint": "A" * 40,
              "notAfter": "2099-02-19T00:00:00Z"}
    filial = {**matriz, "subjectCN": "DELLMAR:13254104000255", "thumbprint": "B" * 40}
    assert select_certificate([filial, matriz], "13.254.104/0001-74") == matriz
    with pytest.raises(RuntimeError, match="mais de um"):
        select_certificate([matriz, {**matriz, "thumbprint": "C" * 40}], "13254104000174")
    assert select_certificate([filial, matriz], "", "B" * 40) == filial
    profile = create_profile(tmp_path, matriz)
    prefs = json.loads((profile / "Default/Preferences").read_text(encoding="utf-8"))
    rule = json.loads(prefs["profile"]["managed_auto_select_certificate_for_urls"][0])
    assert rule == certificate_rule(matriz)
    assert rule["pattern"] == "https://[*.]cte.fazenda.gov.br"
    assert rule["filter"]["SUBJECT"]["CN"] == matriz["subjectCN"]
    remove_profile(tmp_path, profile)
    assert not profile.exists()
    with pytest.raises(ValueError):
        remove_profile(tmp_path, tmp_path.parent)
