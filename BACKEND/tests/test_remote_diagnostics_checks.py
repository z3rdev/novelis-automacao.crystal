import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.domain.remote_diagnostics import DiagnosticOptions
from app.services.remote_diagnostics import checks, probe


def test_certificate_is_matched_to_configuration_without_using_the_private_key(monkeypatch):
    cert = {
        "subjectCN": "TEST 12345678901234",
        "thumbprint": "ABCD",
        "notAfter": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
    }
    monkeypatch.setattr(checks, "windows_certificates", lambda: [cert])
    config = SimpleNamespace(
        xml_sefaz=lambda: {"certificateCnpj": "12345678901234", "certificateThumbprint": "ABCD"}
    )
    result = checks.certificate_check(config)
    assert result["status"] == "ok"
    assert result["details"]["private_key_exported"] is False
    assert result["details"]["private_key_use_tested"] is False
    config.xml_sefaz = lambda: {"certificateCnpj": "99999999999999"}
    assert checks.certificate_check(config)["status"] == "failed"


def test_dll_presence_is_not_success_and_rdc_designtime_is_required(monkeypatch):
    data = {
        "checks": {
            "environment": {
                "compatible": True,
                "prog_id": "CrystalRuntime.Application.11",
                "sqloledb_x86_created": False,
                "engine": {"path": "craxddrt.dll", "loadable": False},
                "native_dlls": [{"path": "crpe32.dll", "loadable": False}],
            },
            "pdf_output": {"engine": "windows", "windows_printer_available": True},
        }
    }
    monkeypatch.setattr(checks, "CrystalReportService", lambda *args: None)

    def diagnose(*args, **kwargs):
        assert kwargs == {"connect": False}  # no document/export requested
        return data

    monkeypatch.setattr(checks, "diagnose", diagnose)
    result = {item["id"]: item for item in checks.crystal_checks(None, None)}
    assert result["crystal"]["status"] == "failed"
    assert result["sqloledb"]["status"] == "failed"
    assert result["dll:craxddrt.dll"]["status"] == "failed"
    assert result["dll:crpe32.dll"]["status"] == "failed"
    assert result["report"]["status"] == "not_tested"


def test_probe_keeps_history_and_current_checks_separate_and_never_creates_fiscal_document(
    monkeypatch, tmp_path
):
    config = SimpleNamespace(values={"SQL_PASS": "fixture-secret"})
    settings = SimpleNamespace(backend_root=tmp_path, novelis_sqlite_path=None)
    monkeypatch.setattr(
        probe,
        "device_identity",
        lambda: {
            "computer_name": "TEST-PC",
            "windows_user": "DOMAIN\\op",
            "mac_addresses": ["hidden"],
        },
    )
    monkeypatch.setattr(probe, "_read_release_version", lambda *args: "test")
    for name in ("system_check", "certificate_check", "database_check", "installation_check"):
        monkeypatch.setattr(
            probe, name, lambda *args: checks.check("safe", "Teste", "ok", "fixture-secret")
        )
    monkeypatch.setattr(probe, "crystal_checks", lambda *args: [])
    frames = []
    result = probe.collect(settings, config, DiagnosticOptions(), frames.append)
    assert frames[0]["complete"] is False and frames[-1]["complete"] is True
    assert result["checks"][-1]["id"] == "fiscal_export"
    assert result["checks"][-1]["status"] == "not_tested"
    assert "mac_addresses" not in result["device"]
    assert "fixture-secret" not in json.dumps(frames)
