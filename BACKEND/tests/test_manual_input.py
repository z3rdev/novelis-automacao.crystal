import asyncio
import base64
from io import BytesIO
from types import SimpleNamespace

from openpyxl import Workbook

from app.automation.flows.pendentes.controles import manual_input
from app.automation.flows.pendentes.controles.manual_input import ManualInputResolver
from app.domain.models import ManualSpreadsheetInput, RunStartRequest
from app.infrastructure.json_store import read_json


async def emit_stub(*args, **kwargs):
    return None


def workbook_payload(rows: list[list[str]]) -> str:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Retornos"
    for row in rows:
        sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    return base64.b64encode(output.getvalue()).decode("ascii")


def test_manual_sequence_accepts_common_formats(tmp_path):
    resolver = ManualInputResolver(tmp_path, emit_stub)

    rows = resolver._rows_from_sequence("2-10-10402\n9;10;287, 11 10 115", {})

    assert [row["documento"] for row in rows] == ["10402", "287", "115"]
    assert all(row["status"] == "AGUARDANDO_MANUAL" for row in rows)


def test_manual_spreadsheet_becomes_source_json(tmp_path):
    resolver = ManualInputResolver(tmp_path, emit_stub)
    request = RunStartRequest(
        flow="pendentes",
        dry_run=False,
        manual_spreadsheet=ManualSpreadsheetInput(
            filename="retornos.xlsx",
            content_base64=workbook_payload(
                [
                    ["Filial", "Serie", "Documento"],
                    ["9", "10", "287"],
                    ["2", "10", "10402"],
                ]
            ),
        ),
    )

    config = asyncio.run(resolver.apply({"refreshSql": True, "refreshNovelisRelatorio": True}, request, "run-1"))

    assert config["refreshSql"] is False
    assert config["refreshNovelisRelatorio"] is False
    assert config["refreshNovelisRelatorioAfterChamados"] is False
    assert config["sourceJson"].endswith("run-1.json")


def test_manual_input_enriches_missing_cte_id_from_sql(tmp_path, monkeypatch):
    def fake_fetch_rows_by_documents(config, rows):
        return SimpleNamespace(
            rows=[
                {
                    "filial": "2",
                    "serie": "10",
                    "documento": "10402",
                    "cteId": "35260813254104000255570100000104021000104020",
                    "__sql": {"enriched": True},
                }
            ],
            source={"manualLookupTotal": len(rows)},
        )

    monkeypatch.setattr(manual_input, "fetch_rows_by_documents", fake_fetch_rows_by_documents)
    resolver = ManualInputResolver(tmp_path, emit_stub)
    request = RunStartRequest(flow="pendentes", dry_run=False, manual_ctes="2-10-10402")

    config = asyncio.run(resolver.apply({}, request, "run-sql", {"enabled": True}))
    payload = read_json(tmp_path / "captures" / "pendentes" / "manual-inputs" / "run-sql.json", {})
    row = payload["rows"][0]

    assert config["sourceJson"].endswith("run-sql.json")
    assert row["cteId"] == "35260813254104000255570100000104021000104020"
    assert row["CTE_ID"] == "35260813254104000255570100000104021000104020"
    assert row["__sql"]["manualLookup"] is True
