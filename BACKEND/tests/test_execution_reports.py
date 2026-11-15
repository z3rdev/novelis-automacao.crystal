import asyncio
import json
from datetime import UTC, datetime
from hashlib import sha256
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.api.routers.execution_reports import router
from app.domain.models import RunSnapshot, RunStartRequest
from app.infrastructure.event_bus import EventBus
from app.infrastructure.operations_store import OperationsStore
from app.services.execution_reports.models import entries, ticket
from app.services.execution_reports.service import ExecutionReports
from app.services.execution_reports.storage import ReportStorage


def sample(number="202611140001"):
    return ticket(
        {
            "filial": 8,
            "serie": 10,
            "documento": 1559,
            "ton": 30,
            "idTarifario": "666318",
            "VLR_TOTAL": 6004.13,
            "VLR_TAR": 4644,
            "REM_CIDADE": "JOAO PESSOA",
            "DES_CIDADE": "CABEDELO",
            "password": "must-not-leak",
        },
        number,
    )


class OfflineStorage:
    def publish(self, value, path):
        raise RuntimeError("offline-test")

    def retrieve(self, value, path):
        assert sha256(path.read_bytes()).hexdigest() == value["sha256"]
        return path


@pytest.fixture
def setup(tmp_path):
    store = OperationsStore(tmp_path / "shared.sqlite", "computer-a")
    store.initialize()
    settings = SimpleNamespace(backend_root=tmp_path / "BACKEND")
    service = ExecutionReports(settings, {}, store, storage=OfflineStorage())
    yield service, store, settings
    asyncio.run(service.close())
    store.close()


def test_only_confirmed_new_saves_count_and_repeated_events_are_deduplicated():
    def event(kind, result=None):
        return {"kind": kind, "payload": {"ticket": sample(), "result": result or {}}}

    opened, existing = entries(
        [
            event("novelis.open_chamado"),
            event("novelis.save"),
            event("novelis.save", {"ok": False}),
            event("novelis.save", {"ok": True}),
            event("novelis.save", {"ok": True}),
            event("novelis.save", {"ok": True, "duplicate": True}),
            event("novelis.chamado_exists"),
        ]
    )
    assert len(opened) == len(existing) == 1
    assert "password" not in opened[0] and "must-not-leak" not in json.dumps(opened)


def test_http_opening_workflow_has_an_execution_report(setup):
    service, _, _ = setup
    snapshot = RunSnapshot(status="running", flow="chamado-http", started_at=datetime.now(UTC))
    asyncio.run(service.begin(snapshot, RunStartRequest(flow="chamado-http", dry_run=False)))
    assert service.repository.get(snapshot.id)["flow"] == "chamado-http"


def finalize(service, store, status="completed"):
    async def exercise():
        started = datetime.now(UTC)
        snapshot = RunSnapshot(status="running", flow="pendentes", started_at=started)
        await service.begin(snapshot, RunStartRequest(flow="pendentes", dry_run=False))
        bus = EventBus(store=store)
        await bus.publish(
            "Saved",
            run_id=snapshot.id,
            kind="novelis.save",
            payload={"ticket": sample(), "result": {"ok": True}},
        )
        await bus.publish(
            "Exists",
            run_id=snapshot.id,
            kind="novelis.chamado_exists",
            payload={"ticket": sample("202611130002")},
        )
        end = snapshot.model_copy(update={"status": status, "finished_at": datetime.now(UTC)})
        value = await service.finish(end)
        await service._job
        return value

    return asyncio.run(exercise())


@pytest.mark.parametrize("status", ["completed", "failed", "cancelled"])
def test_report_includes_partial_confirmed_results_and_survives_s3_failure(setup, status):
    service, store, _ = setup
    report = finalize(service, store, status)
    assert report["status"] == status and report["opened_count"] == report["existing_count"] == 1
    assert service.detail(report["id"])["share_status"] == "pending"
    book = load_workbook(service.download(report["id"]))
    assert book.sheetnames == ["Resumo", "Chamados abertos", "Já existentes"]
    assert book["Chamados abertos"].max_row == 2
    assert book["Chamados abertos"]["B2"].value == "202611140001"
    assert book["Chamados abertos"]["K2"].hyperlink.target.endswith("202611140001")
    assert book["Chamados abertos"]["I2"].value == 6004.13
    book.close()


def test_other_computer_reads_same_catalog_and_download_without_developer_mode(setup):
    service, store, settings = setup
    report = finalize(service, store)
    other = OperationsStore(store.path, "computer-b")
    other.initialize()
    reader = ExecutionReports(settings, {}, other, storage=OfflineStorage())
    assert reader.page()["total"] == 1
    assert reader.download(report["id"]).read_bytes() == service.file(report["id"]).read_bytes()
    other.close()


def test_large_execution_ignores_ui_event_limit_and_does_not_mix_runs(setup):
    service, store, _ = setup
    run_id = str(uuid4())
    other = str(uuid4())
    with store.connection() as db:
        db.executemany(
            "INSERT INTO execution_events(run_id,payload) VALUES (?,?)",
            [
                (
                    run_id,
                    json.dumps(
                        {
                            "kind": "novelis.save",
                            "payload": {
                                "ticket": {**sample(), "cte": f"8-10-{i}"},
                                "result": {"ok": True},
                            },
                        }
                    ),
                )
                for i in range(1101)
            ],
        )
        db.execute(
            "INSERT INTO execution_events(run_id,payload) VALUES (?,?)",
            (other, json.dumps({"kind": "novelis.save"})),
        )
    opened, _ = entries(service.repository.events(run_id))
    assert len(opened) == 1101


def test_excel_strings_are_not_evaluated_as_formulas(setup):
    from app.services.execution_reports.workbook import build

    service, store, _ = setup
    report = finalize(service, store)
    data = service.repository.get(report["id"])
    data["operator"] = '=HYPERLINK("https://invalid.example","click")'
    data["opened"][0]["origem"] = "=1+1"
    build(data, service.file(report["id"]))
    book = load_workbook(service.file(report["id"]))
    assert book["Resumo"]["B3"].data_type == "s"
    assert book["Chamados abertos"]["D2"].data_type == "s"
    book.close()


def test_authenticated_api_hides_signing_url_and_downloads_exact_report(setup):
    service, store, _ = setup
    report = finalize(service, store)
    service.download(report["id"])
    data = service.repository.get(report["id"])
    data.update(
        private_url="must-not-expose",
        object_key="private-object",
        sha256=sha256(service.file(report["id"]).read_bytes()).hexdigest(),
    )
    service.repository.save(data)
    app = FastAPI()
    app.state.execution_reports = service
    app.state.session_audit = SimpleNamespace(
        session=lambda value: {"id": value} if value == "operator-test" else None
    )
    app.include_router(router)
    with TestClient(app) as client:
        assert client.get("/hub/execution-reports").status_code == 401
        client.headers["X-Operator-Session"] = "operator-test"
        assert "must-not-expose" not in client.get("/hub/execution-reports").text
        detail = client.get(f"/hub/execution-reports/{report['id']}")
        assert (
            detail.status_code == 200
            and "private_url" not in detail.text
            and "sha256" not in detail.text
        )
        response = client.get(f"/hub/execution-reports/{report['id']}/file")
        assert (
            response.status_code == 200
            and response.content == service.file(report["id"]).read_bytes()
        )
        assert client.get("/hub/execution-reports/not-a-uuid/file").status_code == 422


@pytest.mark.parametrize(
    "resource,blocked",
    [("cargo-hub/*", True), ("cargo-hub/reports/*", True), ("cargo-hub/packages/*", False)],
)
def test_private_reports_cannot_be_uploaded_into_a_public_prefix(resource, blocked):
    client = SimpleNamespace(
        get_bucket_policy=lambda **kwargs: {
            "Policy": json.dumps(
                {
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"AWS": ["*"]},
                            "Action": ["s3:GetObject"],
                            "Resource": ["arn:aws:s3:::z3-releases/" + resource],
                        }
                    ]
                }
            )
        }
    )
    if blocked:
        with pytest.raises(RuntimeError, match="pública"):
            ReportStorage.ensure_private(client, "cargo-hub/reports/executions/id/report.xlsx")
    else:
        ReportStorage.ensure_private(client, "cargo-hub/reports/executions/id/report.xlsx")


@pytest.mark.parametrize("failed", [False, True])
def test_real_automation_finalizer_generates_report_without_changing_fiscal_result(
    setup, monkeypatch, failed
):
    from unittest.mock import AsyncMock

    from app.domain.run_state import RunState
    from app.services.automation_service import AutomationService

    service, store, settings = setup
    settings.consulta_browser_headless = False
    bus = EventBus(store=store)

    async def flow(request, run_id, browser):
        await bus.publish(
            "Save confirmed",
            run_id=run_id,
            kind="novelis.save",
            payload={"ticket": sample(), "result": {"ok": True}},
        )
        if failed:
            raise RuntimeError("Second document failed (fixture)")
        return {}

    monkeypatch.setattr(
        "app.services.automation_service.LegacyCoordinator", lambda *args: SimpleNamespace(run=flow)
    )
    monkeypatch.setattr("app.services.automation_service.clean_capture_roots", lambda *args: {})
    automation = AutomationService(
        settings,
        None,
        None,
        bus,
        RunState(store),
        SimpleNamespace(close=AsyncMock()),
        run_reports=service,
    )

    async def exercise():
        snapshot = await automation.start(RunStartRequest(flow="pendentes", dry_run=False))
        await automation._task
        if service._job:
            await service._job
        assert (await automation.current()).status == ("failed" if failed else "completed")
        assert service.detail(snapshot.id)["opened_count"] == 1
        assert service.download(snapshot.id).is_file()

    asyncio.run(exercise())


def test_minio_metadata_names_are_case_insensitive(setup):
    service, store, settings = setup
    report = finalize(service, store)
    service.download(report["id"])
    value = service.repository.get(report["id"])
    file = service.file(report["id"])
    client = SimpleNamespace(
        get_bucket_policy=lambda **kwargs: {"Policy": '{"Statement":[]}'},
        upload_file=lambda *args, **kwargs: None,
        head_object=lambda **kwargs: {
            "Metadata": {"Sha256": value["sha256"]},
            "ContentLength": file.stat().st_size,
        },
        generate_presigned_url=lambda *args, **kwargs: "signed-url-test-only",
    )
    storage = ReportStorage(settings.backend_root, {})
    storage.client = lambda: client
    result = storage.publish(value, file)
    assert result["share_status"] == "shared"


def test_report_keeps_the_operator_who_started_the_run_even_after_logout(setup):
    from app.services.session_audit import operator_session

    service, _, _ = setup
    service.audit = SimpleNamespace(
        session=lambda value: {"operator_name": "Operador original"},
        identity=lambda: {"windows_user": "Windows-test"},
    )

    async def exercise():
        snapshot = RunSnapshot(flow="pendentes", status="running", started_at=datetime.now(UTC))
        token = operator_session.set("owner-session")
        try:
            await service.begin(snapshot, RunStartRequest(flow="pendentes", dry_run=False))
        finally:
            operator_session.reset(token)
        service.audit.session = lambda value: None
        await service.finish(
            snapshot.model_copy(update={"status": "completed", "finished_at": datetime.now(UTC)})
        )
        await service._job
        assert service.detail(snapshot.id)["operator"] == "Operador original"

    asyncio.run(exercise())
