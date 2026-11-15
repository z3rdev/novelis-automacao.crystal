import asyncio
from io import BytesIO

import httpx
import pytest
from openpyxl import Workbook

from app.services.novelis_report_http import ReportDownloadError, download_report


def excel(headers=("ID", "SERIE", "NCT", "CHAMADO")):
    book = Workbook()
    book.active.append(list(headers))
    stream = BytesIO()
    book.save(stream)
    return stream.getvalue()


def test_authenticated_export_uses_portal_form_and_dates_without_browser(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path == "/login":
            if request.method == "GET":
                return httpx.Response(200, headers={"set-cookie": "XSRF-TOKEN=test-csrf; Path=/"})
            assert request.headers["X-XSRF-TOKEN"] == "test-csrf"
            return httpx.Response(302, headers={"location": "/portal"})
        if request.method == "GET":
            return httpx.Response(
                200,
                text='<form id="form"><input name="_token" type="hidden" value="csrf-form"><input name="de"><input name="ate"></form>',
            )
        assert request.url.path == "/custom/relatorio_cte_xml_excel"
        assert b"de=01%2F11%2F2026" in request.content and b"tipo=date" in request.content
        assert b"_token=csrf-form" in request.content
        return httpx.Response(200, content=excel())

    result = asyncio.run(
        download_report(
            {"user": "test", "pass": "test"},
            {"startBR": "01/11/2026", "endBR": "14/11/2026"},
            tmp_path / "report.xlsx",
            transport=httpx.MockTransport(handler),
        )
    )
    assert result["transport"] == "http" and result["file"].read_bytes().startswith(b"PK")
    assert len(calls) == 4


@pytest.mark.parametrize(
    "content,status", [(b"<html>login</html>", 200), (excel(("OTHER",)), 200), (b"", 302)]
)
def test_invalid_export_preserves_previous_excel_and_removes_partial_files(
    tmp_path, content, status
):
    output = tmp_path / "report.xlsx"
    output.write_bytes(b"previous-valid-file")

    def handler(request):
        if request.url.path == "/login":
            return httpx.Response(200)
        if request.method == "GET":
            return httpx.Response(
                200, text='<form id="form"><input name="de"><input name="ate"></form>'
            )
        return httpx.Response(status, content=content)

    with pytest.raises(ReportDownloadError):
        asyncio.run(
            download_report(
                {"user": "test", "pass": "secret-test"},
                {"startBR": "01/11/2026", "endBR": "14/11/2026"},
                output,
                transport=httpx.MockTransport(handler),
            )
        )
    assert output.read_bytes() == b"previous-valid-file"
    assert not list(tmp_path.glob("*.tmp"))


def test_login_redirect_cannot_forward_credentials_or_export_to_another_host(tmp_path):
    calls = []

    def handler(request):
        calls.append(request.url.host)
        return (
            httpx.Response(302, headers={"location": "https://invalid.example/collect"})
            if request.method == "POST"
            else httpx.Response(200)
        )

    with pytest.raises(ReportDownloadError):
        asyncio.run(
            download_report(
                {"user": "test", "pass": "secret-test"},
                {},
                tmp_path / "a.xlsx",
                transport=httpx.MockTransport(handler),
            )
        )
    assert set(calls) == {"novelis.wtmh.com.br"}


def test_report_flow_can_export_without_any_browser_instance(tmp_path, monkeypatch):
    from unittest.mock import AsyncMock

    from app.automation.flows.novelis_relatorio.steps.novelis_relatorio_cte_xml import (
        NovelisRelatorioCteXmlFlow,
    )

    output = tmp_path / "report.xlsx"
    output.write_bytes(excel())
    export = AsyncMock(
        return_value={
            "file": output,
            "sourceUrl": "https://novelis.wtmh.com.br/custom/relatorio_cte_xml",
            "suggestedName": "report.xlsx",
            "dateRange": {"startBR": "01/11/2026", "endBR": "14/11/2026"},
        }
    )
    monkeypatch.setattr("app.services.novelis_report_http.download_report", export)
    flow = NovelisRelatorioCteXmlFlow(tmp_path, AsyncMock())
    result = asyncio.run(
        flow.run(None, {"relatorioCteXmlSkipIfFreshToday": False}, [], "run-fixture")
    )
    export.assert_awaited_once()
    assert not result["skipped"] and result["payload"]["totalUniqueCte"] == 0
