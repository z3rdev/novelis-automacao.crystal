import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.routers.reports import get_crystal_service, router
from app.services.crystal_reports.models import DacteRequest
from app.services.crystal_reports.service import CrystalReportError, CrystalReportService


class ConfigStub:
    def __init__(self, report_path: Path, password: str = "test-secret"):
        self.report_path = report_path
        self.password = password

    def get(self, key, fallback=""):
        # Worker protocol tests explicitly exercise the preserved report renderer.
        if key == "CRYSTAL_QR_PROVIDER":
            return "report"
        return str(self.report_path) if key == "CRYSTAL_DACTE_RPT_PATH" else fallback

    def int(self, key, fallback):
        return fallback

    def consulta_db(self):
        return {"server": "test", "database": "test", "user": "test", "pass": self.password}


@pytest.fixture
def service(tmp_path):
    report = tmp_path / "report.rpt"
    report.write_bytes(b"test")
    return CrystalReportService(SimpleNamespace(storage_dir=tmp_path), ConfigStub(report))


def document():
    return DacteRequest(filial=2, serie="10", documento=17419)


@pytest.mark.parametrize(
    "changes",
    [
        {"filial": 0},
        {"documento": -1},
        {"serie": "../10"},
        {"serie": "10;DROP"},
        {"output_path": "C:/test.pdf"},
        {"password": "secret"},
    ],
)
def test_request_rejects_invalid_identifiers_and_extra_fields(changes):
    with pytest.raises(ValidationError):
        DacteRequest(**{**document().model_dump(), **changes})


def test_export_requires_configured_credentials(service):
    service.config.password = ""
    with pytest.raises(CrystalReportError, match="CONSULTA_DB"):
        service.export(document())


def test_unknown_pdf_engine_is_rejected_before_starting_crystal(service, monkeypatch):
    original_get = service.config.get
    monkeypatch.setattr(
        service.config, "get",
        lambda key, default="": "physical-printer" if key == "CRYSTAL_PDF_ENGINE" else original_get(key, default),
    )
    with pytest.raises(CrystalReportError, match="windows ou native"):
        service.export(document())


def test_failed_export_removes_partial_file(service, monkeypatch):
    def fail(payload):
        Path(payload["output_path"]).write_bytes(b"partial")
        raise CrystalReportError("failure")

    monkeypatch.setattr(service, "_execute", fail)
    with pytest.raises(CrystalReportError):
        service.export(document())
    assert not list(service.settings.storage_dir.rglob("*.pdf"))


def test_export_rejects_non_pdf_engine_output(service, monkeypatch):
    def invalid(payload):
        Path(payload["output_path"]).write_bytes(b"not a pdf document")

    monkeypatch.setattr(service, "_execute", invalid)
    with pytest.raises(CrystalReportError, match="nao e PDF"):
        service.export(document())
    assert not list(service.settings.storage_dir.rglob("*.pdf"))


@pytest.mark.skipif(os.name != "nt", reason="Worker requer Windows PowerShell 32 bits")
def test_timeout_releases_worker_lock(service, monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 120)

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(CrystalReportError) as error:
        service.inspect()
    assert error.value.status_code == 504
    assert service._lock.acquire(blocking=False)
    service._lock.release()


@pytest.mark.skipif(os.name != "nt", reason="Worker requer Windows PowerShell 32 bits")
def test_credentials_use_stdin_and_engine_errors_redact_password(service, monkeypatch):
    def failed_worker(command, **kwargs):
        assert "test-secret" not in " ".join(command)
        assert json.loads(kwargs["input"])["database"]["password"] == "test-secret"
        return SimpleNamespace(
            returncode=1,
            stdout=json.dumps(
                {"ok": False, "stage": "database", "error": "Connection failed: test-secret"}
            ),
        )

    monkeypatch.setattr(subprocess, "run", failed_worker)
    with pytest.raises(CrystalReportError) as error:
        service.export(document())
    assert "test-secret" not in str(error.value)
    assert "<redacted>" in str(error.value)


@pytest.mark.skipif(os.name != "nt", reason="Worker requer Windows PowerShell 32 bits")
def test_missing_ufl_returns_dependency_error(service, monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1,
            stdout=json.dumps(
                {"ok": False, "stage": "records", "error": "UFL u2lcom.dll is missing"}
            ),
        ),
    )
    with pytest.raises(CrystalReportError) as error:
        service.export(document())
    assert error.value.status_code == 503
    assert "/api/reports/dacte/inspect" in str(error.value)


@pytest.mark.skipif(os.name != "nt", reason="Worker requer Windows PowerShell 32 bits")
def test_native_license_messages_do_not_corrupt_worker_protocol(service, monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout='Native library warning\nCRYSTAL_RESULT={"ok":true,"environment":{}}\n',
        ),
    )
    assert service._execute({"action": "environment"})["ok"] is True


def test_api_returns_pdf_attachment_and_validates_request(tmp_path):
    output = tmp_path / "test.pdf"
    output.write_bytes(b"%PDF-test-response")
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_crystal_service] = lambda: SimpleNamespace(
        export=lambda doc: output
    )
    client = TestClient(app)
    response = client.post("/reports/dacte/pdf", json=document().model_dump())
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["cache-control"] == "no-store"
    assert "dacte-2-10-17419.pdf" in response.headers["content-disposition"]
    assert response.content == output.read_bytes()
    invalid = client.post("/reports/dacte/pdf", json={**document().model_dump(), "serie": "../"})
    assert invalid.status_code == 422
