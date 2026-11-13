import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.automation.flows.pendentes.controles import crystal_pdf
from app.automation.flows.pendentes.controles.pdf_source import select_pdf_runner
from app.automation.flows.pendentes.steps.pendentes import PendentesFlow
from app.domain.models import RunStartRequest
from app.services.crystal_reports.service import CrystalReportError

KEY = "35" + "2601" + "12345678000199" + "57" + "010" + "000023167" + "1" + "12345678" + "0"
QR = "https://example.test/cte?chCTe=" + KEY


class Config:
    def __init__(self, root, source="crystal", enabled=False):
        self.root, self.source, self.enabled = root, source, enabled

    def get(self, key, default=""):
        return self.source if key == "PENDENTES_PDF_SOURCE" else default

    def bool(self, key, default=False):
        return self.enabled if key == "RODOPAR_BROWSER_ENABLED" else default

    def pendentes(self):
        return {"sourceJson": str(self.root / "rows.json"), "outputFile": str(self.root / "plan.json"),
                "skipNovelis": True, "skipComprovantes": True, "skipXml": True,
                "requireNovelisFilterBeforeExecution": False}

    def rodopar_pdf(self):
        return {"downloadTargetDir": str(self.root / "pdfs"), "defaultSerie": "10"}

    def consulta_db(self):
        return {"enabled": False}

    def xml_sefaz(self):
        return {"downloadDir": str(self.root / "xmls")}

    def comprovante_local(self):
        return {"targetDir": str(self.root / "proofs")}

    def chamado_novelis(self):
        return {}


class NoBrowser:
    def __getattr__(self, name):
        raise AssertionError("O PDF Crystal nao pode acessar o navegador: " + name)


@pytest.fixture
def scenario(tmp_path, monkeypatch):
    source = tmp_path / "generated.pdf"
    source.write_bytes(b"%PDF-test-generated")
    config = Config(tmp_path)
    service = SimpleNamespace(export=lambda document: source)
    monkeypatch.setattr(crystal_pdf, "CrystalReportService", lambda *args: service)
    monkeypatch.setattr(crystal_pdf, "read_pdf_symbols", lambda path: ([
        {"format": "Code 128", "value": KEY}, {"format": "QR Code", "value": QR},
    ], ""))
    settings = SimpleNamespace(backend_root=tmp_path / "BACKEND")
    flow = PendentesFlow(settings, config, None, AsyncMock())
    flow._run_rodopar_pdf = AsyncMock(side_effect=AssertionError("Rodopar nao deve executar"))
    (tmp_path / "rows.json").write_text(json.dumps({"rows": [
        {"filial": "1", "serie": "10", "documento": "23167"},
    ]}))
    return flow, source, service


def test_main_flow_generates_crystal_pdf_without_accessing_browser(scenario):
    flow, source, _ = scenario
    result = asyncio.run(flow.run(NoBrowser(), RunStartRequest(
        flow="pendentes", dry_run=False, sample_cte="1-10-23167",
    ), "test-crystal"))
    target = source.parent / "pdfs/cte-23167/CTE_1-10-23167.pdf"
    assert target.read_bytes() == source.read_bytes()
    assert result["faltandoPdf"] == []
    flow._run_rodopar_pdf.assert_not_awaited()


def test_failed_crystal_never_falls_back_to_rodopar(scenario):
    flow, source, service = scenario

    def fail(document):
        raise CrystalReportError("Runtime indisponivel")

    service.export = fail
    with pytest.raises(RuntimeError, match="Runtime indisponivel"):
        asyncio.run(flow.run(NoBrowser(), RunStartRequest(
            flow="pendentes", dry_run=False, sample_cte="1-10-23167",
        ), "test-failure"))
    flow._run_rodopar_pdf.assert_not_awaited()
    assert not (source.parent / "pdfs").exists()


def test_demo_pdf_stays_local_and_cannot_become_an_attachment(scenario, monkeypatch):
    flow, source, _ = scenario
    monkeypatch.setattr(crystal_pdf, "read_pdf_symbols", lambda path: ([
        {"format": "Code 128", "value": KEY}, {"format": "QR Code", "value": QR + " Demo"},
    ], ""))
    with pytest.raises(RuntimeError, match="componente DEMO"):
        asyncio.run(flow.run(NoBrowser(), RunStartRequest(
            flow="pendentes", dry_run=False, sample_cte="1-10-23167",
        ), "test-demo"))
    assert source.is_file()
    assert not (source.parent / "pdfs").exists()
    flow._run_rodopar_pdf.assert_not_awaited()


def test_legacy_runner_is_preserved_but_requires_explicit_enable(scenario):
    flow, _, _ = scenario
    flow.legacy_config.source = "rodopar"
    with pytest.raises(RuntimeError, match="desabilitado"):
        select_pdf_runner(flow)
    flow.legacy_config.enabled = True
    assert select_pdf_runner(flow) is flow._run_rodopar_pdf


def test_publication_preserves_existing_evidence(tmp_path):
    source, target = tmp_path / "new.pdf", tmp_path / "old.pdf"
    source.write_bytes(b"new")
    target.write_bytes(b"existing")
    crystal_pdf.publish_pdf(source, target)
    assert target.read_bytes() == b"existing"
    assert not list(tmp_path.glob("*.part"))


@pytest.mark.parametrize("legacy", [False, True])
def test_existing_pdf_is_reused_even_when_plan_is_stale(scenario, legacy):
    flow, source, service = scenario
    root = source.parent / "pdfs"
    directory = root / "cte-23167" if legacy else root
    directory.mkdir(parents=True)
    existing = directory / "CTE_1-10-23167.pdf"
    existing.write_bytes(b"%PDF-existing-evidence")
    service.export = lambda *a: pytest.fail("PDF existente nao deve ser gerado novamente")
    runner = select_pdf_runner(flow)
    asyncio.run(runner(None, {"downloadTargetDir": str(root)}, {
        "checked": [{"cte": "1-10-23167", "row": {"filial": 1, "serie": 10, "documento": 23167}}],
        "faltandoPdf": ["1-10-23167"],
    }, RunStartRequest(dry_run=False), "stale-plan", {}))
    assert existing.read_bytes() == b"%PDF-existing-evidence"
    assert len(list(root.rglob("*.pdf"))) == 1
