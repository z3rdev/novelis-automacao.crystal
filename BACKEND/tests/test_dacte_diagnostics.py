import hashlib
import json
from types import SimpleNamespace

import pytest

from app.services.crystal_reports.diagnostics import diagnose
from app.services.crystal_reports.models import DacteRequest
from app.services.crystal_reports.service import CrystalReportError


def test_export_timeout_never_reports_technical_success(tmp_path, monkeypatch):
    report_path = tmp_path / "dacte.rpt"
    report_path.write_bytes(b"report")
    report_path.with_suffix(".manifest.json").write_text(
        json.dumps({"sha256": hashlib.sha256(b"report").hexdigest(), "required_fonts": []})
    )

    def execute(payload):
        if payload["action"] == "environment":
            return {"environment": {
                "compatible": True, "fonts": [], "bcs_functions": {"available": True},
                "native_dlls": [{"loadable": True}],
                "windows_pdf_printer_available": True,
            }}
        return {"reports": [{"formulas": [], "credential_fields": []}]}

    def export(document):
        raise CrystalReportError("Tempo limite excedido no Crystal Reports (records).", 504)

    service = SimpleNamespace(
        report_path=report_path, _execute=execute, export=export,
        config=SimpleNamespace(get=lambda key, default="": default),
        settings=SimpleNamespace(storage_dir=tmp_path),
    )
    monkeypatch.setattr("app.services.crystal_reports.diagnostics.report_database", lambda config: {})
    result = diagnose(service, document=DacteRequest(filial=1, serie="10", documento=23167))
    assert result["dependencies_ready"] is True
    assert result["status"] == "pending"
    assert result["production_ready"] is False
    assert result["checks"]["export"]["status"] == "failed"
    assert result["checks"]["symbols"]["status"] == "not_tested"


@pytest.mark.parametrize("provider,ready", [("python", True), ("report", False)])
def test_only_the_independent_qr_can_be_ready_without_barcodesoft(tmp_path, provider, ready):
    report_path = tmp_path / "dacte.rpt"
    report_path.write_bytes(b"report")
    report_path.with_suffix(".manifest.json").write_text(json.dumps({
        "sha256": hashlib.sha256(b"report").hexdigest(),
        "required_fonts": ["BcsQrcode", "IDAutomationSC128L DEMO"],
    }))

    def execute(payload):
        if payload["action"] == "environment":
            return {"environment": {
                "compatible": True, "fonts": ["IDAutomationSC128L DEMO"],
                "bcs_functions": {"available": False},
                "native_dlls": [{"loadable": True}],
                "windows_pdf_printer_available": True,
            }}
        return {"reports": [{"formulas": [], "credential_fields": []}]}

    class Config:
        def get(self, key, default=""):
            return provider if key == "CRYSTAL_QR_PROVIDER" else default

        def consulta_db(self):
            return {}

    service = SimpleNamespace(
        report_path=report_path, _execute=execute, config=Config(),
        settings=SimpleNamespace(storage_dir=tmp_path),
    )
    result = diagnose(service)
    assert result["dependencies_ready"] is ready
    assert result["checks"]["qr_renderer"]["barcodesoft_required"] is (provider == "report")
    assert result["checks"]["fonts"]["missing"] == ([] if ready else ["BcsQrcode"])
