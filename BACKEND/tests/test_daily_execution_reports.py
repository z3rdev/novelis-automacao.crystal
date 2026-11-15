import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from hashlib import sha256
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.api.routers.execution_reports import router
from app.infrastructure.operations_store import OperationsStore
from app.services.execution_reports.service import ExecutionReports
from app.services.execution_reports.storage import ReportStorage


class Storage:
    def publish(self, value, path):
        assert sha256(path.read_bytes()).hexdigest() == value["sha256"]
        return {
            **value,
            "share_status": "shared",
            "private_url": "private-test",
            "private_url_expires": "2099-01-01T00:00:00+00:00",
        }

    def retrieve(self, value, path):
        assert sha256(path.read_bytes()).hexdigest() == value["sha256"]
        return path


@pytest.fixture
def services(tmp_path):
    store = OperationsStore(tmp_path / "shared.sqlite", "pc-a")
    store.initialize()
    settings = SimpleNamespace(backend_root=tmp_path / "BACKEND")
    service = ExecutionReports(settings, {}, store, storage=Storage())
    yield service, store, settings
    store.close()


def opening(number, moment="2026-11-15T00:20:00+00:00"):
    return {
        "cte": f"8-10-{number}",
        "numero": str(number),
        "confirmado_em": moment,
        "link": f"https://novelis.wtmh.com.br/portal/chamado/{number}",
        "origem": "JOAO PESSOA",
        "destino": "CABEDELO",
        "ton": "30",
        "frete": 4644,
        "valor": 6004.13,
    }


def source(service, opened, *, operator="Ana", computer="pc-a", status="completed", run_id=None):
    value = {
        "id": run_id or str(uuid4()),
        "operator": operator,
        "computer": computer,
        "flow": "pendentes",
        "status": status,
        "started_at": "2026-11-15T00:00:00Z",
        "finished_at": "2026-11-15T04:00:00Z",
        "generated_at": datetime.now(UTC).isoformat(),
        "opened": opened,
        "opened_count": len(opened),
        "existing": [],
        "existing_count": 0,
        "share_status": "pending",
    }
    service.repository.save(value)
    return value


def test_one_day_combines_all_operators_and_partial_runs_without_duplicates(services):
    service, _, _ = services
    source(service, [opening(101), opening(102)])
    source(
        service, [opening(102), opening(103)], operator="Bruno", computer="pc-b", status="failed"
    )
    source(service, [opening(104)], status="cancelled")
    source(service, [])
    source(service, [opening(999)], status="running")
    page = service.page()
    assert page["total"] == 1
    daily = service.detail(page["rows"][0]["id"])
    assert daily["report_date"] == "2026-11-14"
    assert daily["opened_count"] == 4
    assert daily["operators"] == ["Ana", "Bruno"]
    assert daily["computers"] == ["pc-a", "pc-b"]
    assert daily["run_count"] == 3
    assert {item["numero"] for item in daily["opened"]} == {"101", "102", "103", "104"}
    assert "source_revision" not in daily
    path = service.download(daily["id"])
    assert path.name == "2026-11-14.xlsx"
    book = load_workbook(path)
    assert book.sheetnames == ["Resumo", "Chamados abertos"]
    sheet = book["Chamados abertos"]
    assert sheet.max_row == 5
    assert sheet["C2"].value == "14/11/2026 21:20:00"
    assert sheet["L1"].value == "Operador" and sheet["M1"].value == "Computador"
    assert sheet["N1"].value == "Execução"
    assert sheet["B2"].data_type == "s" and sheet["I2"].value == 6004.13
    book.close()
    assert not list(service.root.glob("*.xlsx"))


def test_midnight_is_split_by_confirmation_date_in_sao_paulo(services):
    service, _, _ = services
    source(service, [opening(101, "2026-11-15T02:59:59Z"), opening(102, "2026-11-15T03:00:00Z")])
    source(service, [opening(101, "2026-11-15T03:05:00Z")])
    rows = service.page()["rows"]
    assert [row["report_date"] for row in rows] == ["2026-11-15", "2026-11-14"]
    assert [row["opened_count"] for row in rows] == [1, 1]
    assert service.detail(rows[0]["id"])["opened"][0]["numero"] == "102"


def test_updates_same_daily_report_and_repeated_reads_keep_exact_excel(services):
    service, _, _ = services
    source(service, [opening(101)])
    initial = service.page()["rows"][0]
    path = service.download(initial["id"])
    initial_bytes = path.read_bytes()
    generated_at = initial["generated_at"]
    service.daily.publish(initial["id"])
    assert service.page()["rows"][0]["share_status"] == "shared"
    assert path.read_bytes() == initial_bytes
    assert service.page()["rows"][0]["generated_at"] == generated_at
    source(service, [opening(102)], operator="Bruno")
    updated = service.page()["rows"][0]
    assert updated["id"] == initial["id"] and updated["opened_count"] == 2
    assert updated["share_status"] == "pending"
    assert path.read_bytes() != initial_bytes
    assert service.page()["total"] == 1
    assert len(list(service.daily.root.glob("*.xlsx"))) == 1


def test_concurrent_refresh_and_publish_keep_all_openings(services):
    service, store, settings = services
    other_store = OperationsStore(store.path, "pc-b")
    other_store.initialize()
    other = ExecutionReports(settings, {}, other_store, storage=Storage())
    source(service, [opening(101)])
    daily_id = service.page()["rows"][0]["id"]
    entered, release, refresh_started = Event(), Event(), Event()
    published = []

    def publish(value, path):
        entered.set()
        assert release.wait(10)
        published.append(value["opened_count"])
        return Storage().publish(value, path)

    def refresh():
        refresh_started.set()
        return other.page()

    service.daily.storage = SimpleNamespace(publish=publish, retrieve=Storage().retrieve)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            publication = executor.submit(service.daily.publish, daily_id)
            assert entered.wait(10)
            source(other, [opening(102)], operator="Bruno", computer="pc-b")
            updated = executor.submit(refresh)
            assert refresh_started.wait(10)
            release.set()
            publication.result(timeout=10)
            assert updated.result(timeout=10)["rows"][0]["opened_count"] == 2
        other.daily.publish(daily_id)
        final = service.detail(daily_id)
        assert published == [1]
        assert final["opened_count"] == 2 and final["share_status"] == "shared"
        assert service.download(daily_id).is_file()
    finally:
        release.set()
        other_store.close()


def test_daily_s3_uses_same_object_key_after_more_openings(services):
    service, _, settings = services
    uploaded, contents = [], {}

    def upload(path, bucket, key, ExtraArgs):
        uploaded.append(key)
        from pathlib import Path

        contents[key] = (Path(path).read_bytes(), ExtraArgs["Metadata"])

    client = SimpleNamespace(
        get_bucket_policy=lambda **kwargs: {"Policy": '{"Statement":[]}'},
        upload_file=upload,
        head_object=lambda **kwargs: {
            "ContentLength": len(contents[kwargs["Key"]][0]),
            "Metadata": contents[kwargs["Key"]][1],
        },
        generate_presigned_url=lambda *args, **kwargs: "private-test",
    )
    storage = ReportStorage(settings.backend_root, {})
    storage.client = lambda: client
    service.daily.storage = storage
    source(service, [opening(101)])
    daily_id = service.page()["rows"][0]["id"]
    service.daily.publish(daily_id)
    source(service, [opening(102)])
    service.page()
    service.daily.publish(daily_id)
    assert uploaded == ["cargo-hub/reports/daily/2026/11/14/report.xlsx"] * 2
    assert len(contents) == 1


def test_api_lists_daily_reports_and_downloads_date_named_excel(services):
    service, _, _ = services
    source(service, [opening(101)])
    source(service, [opening(102)])
    app = FastAPI()
    app.state.execution_reports = service
    app.state.session_audit = SimpleNamespace(session=lambda value: {"id": value})
    app.include_router(router)
    with TestClient(app) as client:
        assert client.get("/hub/execution-reports").status_code == 401
        client.headers["X-Operator-Session"] = "operator-test"
        response = client.get("/hub/execution-reports")
        assert response.status_code == 200
        assert response.json()["total"] == 1
        value = response.json()["rows"][0]
        assert value["opened_count"] == 2
        assert "source_revision" not in response.text
        download = client.get(f"/hub/execution-reports/{value['id']}/file")
        assert download.status_code == 200
        assert "CargoHub-Chamados-2026-11-14.xlsx" in download.headers["content-disposition"]
        assert "private_url" not in json.dumps(value)
