from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers.reports import get_xml_service, router
from app.services.crystal_reports.models import DacteRequest
from app.services.crystal_reports.service import CrystalReportError
from app.services.dacte_xml import XmlDacteService, validate_cte_xml

KEY = "35" + "2611" + "12345678000199" + "57" + "010" + "000023167" + "1" + "00000000" + "0"


def document():
    return DacteRequest(filial=1, serie="10", documento=23167)


def xml_content(status="100", number="23167", model="57", key=KEY):
    return f"""<cteProc xmlns="http://www.portalfiscal.inf.br/cte" versao="4.00">
      <CTe><infCte Id="CTe{KEY}"><ide><mod>{model}</mod><serie>10</serie>
      <nCT>{number}</nCT></ide></infCte></CTe>
      <protCTe><infProt><chCTe>{key}</chCTe><cStat>{status}</cStat></infProt></protCTe>
    </cteProc>""".encode()


def test_xml_identity_matches_document_and_protocol():
    assert "cteProc" in validate_cte_xml(xml_content(), document())


@pytest.mark.parametrize(
    "content",
    [
        xml_content(status="101"),
        xml_content(number="23168"),
        xml_content(model="67"),
        xml_content(key="0" * 44),
        b"<not-xml",
        b"<CTe />",
        b'<!DOCTYPE x [<!ENTITY sample "test">]><CTe />',
    ],
)
def test_invalid_or_mismatched_xml_is_rejected(content):
    with pytest.raises(CrystalReportError) as error:
        validate_cte_xml(content, document())
    assert error.value.status_code == 422


def test_wrong_series_is_rejected():
    with pytest.raises(CrystalReportError):
        validate_cte_xml(xml_content(), DacteRequest(filial=1, serie="11", documento=23167))


def test_missing_xml_returns_not_found(tmp_path):
    service = XmlDacteService(
        SimpleNamespace(storage_dir=tmp_path),
        SimpleNamespace(xml_sefaz=lambda: {"downloadDir": str(tmp_path)}),
    )
    with pytest.raises(CrystalReportError) as error:
        service.export(document())
    assert error.value.status_code == 404


def test_xml_api_identifies_renderer_in_response(tmp_path):
    output = tmp_path / "test.pdf"
    output.write_bytes(b"%PDF-test-xml-response")
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_xml_service] = lambda: SimpleNamespace(export=lambda doc: output)
    response = TestClient(app).post("/reports/dacte/pdf-from-xml", json=document().model_dump())
    assert response.status_code == 200
    assert response.headers["x-dacte-source"] == "xml"
    assert response.headers["content-type"] == "application/pdf"
    assert "dacte-1-10-23167-xml.pdf" in response.headers["content-disposition"]


def test_xml_api_reports_missing_source():
    def missing(document):
        raise CrystalReportError("XML nao encontrado", 404)

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_xml_service] = lambda: SimpleNamespace(export=missing)
    response = TestClient(app).post("/reports/dacte/pdf-from-xml", json=document().model_dump())
    assert response.status_code == 404
