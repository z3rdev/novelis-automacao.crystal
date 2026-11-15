import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from app.services.crystal_reports.diagnostic_view import render_diagnostic
from app.services.crystal_reports.diagnostics import write_diagnostic


def report():
    return {
        "schema_version": 1,
        "checked_at": "2026-11-15T03:53:00Z",
        "status": "technical_ready",
        "dependencies_ready": True,
        "production_ready": False,
        "fiscal_validation": "pending",
        "checks": {
            "environment": {
                "com_created": True,
                "prog_id": "CrystalDesignRunTime.Application.11",
                "process_bits": 32,
                "sqloledb_x86_created": True,
                "engine": {
                    "path": r"C:\Runtime\craxddrt.dll",
                    "loadable": True,
                    "version": "11.5.0.313",
                    "architecture": "x86",
                },
                "native_dlls": [{"path": r"C:\Runtime\crdb_ado.dll", "loadable": False}],
            },
            "integrity": {"status": "ok"},
            "report": {"status": "ok"},
            "fonts": {"status": "ok", "required": ["Arial"], "missing": []},
            "qr_renderer": {"status": "ok", "provider": "python"},
            "code128_renderer": {"status": "ok", "provider": "python"},
            "database": {"status": "ok"},
            "pdf_output": {"engine": "native"},
            "export": {"status": "not_tested"},
            "symbols": {"status": "not_tested"},
        },
    }


def test_report_groups_results_and_does_not_promote_untested_fiscal_checks():
    html = render_diagnostic(report())
    for label in (
        "Crystal Reports RDC x86",
        "Relatório e geração do DACTE",
        "Conexão e testes com documento",
        "Não testado",
        "não confirmada",
        "crdb_ado.dll",
        "11.5.0.313",
    ):
        assert label in html
    assert "15/11/2026 às 00:53" in html
    assert 'data-status="error"' in html
    assert "<script src=" not in html and "<link " not in html
    assert 'id="download"' in html and 'id="theme"' in html


def test_report_escapes_untrusted_strings_and_redacts_sensitive_fields(tmp_path):
    value = report()
    value["checks"]["report"]["message"] = '<img src=x onerror="alert(1)">'
    value["extra"] = {
        "PIDKEY": "license-fixture-123",
        "password": "password-fixture-987",
        "url": "https://fixture:private-fixture@localhost/path",
        "error": "pwd=private-sql-fixture; token=private-token-fixture",
    }
    write_diagnostic(value, tmp_path)
    html = (tmp_path / "dacte-diagnostic.html").read_text(encoding="utf-8")
    saved = (tmp_path / "dacte-diagnostic.json").read_text(encoding="utf-8")
    for secret in (
        "license-fixture-123",
        "password-fixture-987",
        "private-fixture",
        "private-sql-fixture",
        "private-token-fixture",
    ):
        assert secret not in html and secret not in saved
    assert "<img src=x" not in html and "&lt;img src=x" in html
    assert json.loads(saved)["production_ready"] is False
    assert json.loads(saved)["checks"]["report"]["status"] == "ok"


def test_partial_diagnostic_preserves_failure_and_missing_results():
    html = render_diagnostic(
        {
            "status": "pending",
            "checks": {"environment": {"compatible": False, "error": "COM indisponível."}},
        }
    )
    assert "A instalação precisa de revisão" in html
    assert "COM indisponível." in html
    assert "Data não informada" in html
    assert 'class="status pending">Não testado' in html


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell bootstrap fallback")
def test_missing_python_uses_the_offline_diagnostic_layout(tmp_path):
    root = Path(__file__).resolve().parents[2]
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copy2(root / "scripts/prepare-dacte.ps1", scripts / "prepare-dacte.ps1")
    destination = tmp_path / "BACKEND/app/services/crystal_reports/diagnostic_assets"
    shutil.copytree(root / "BACKEND/app/services/crystal_reports/diagnostic_assets", destination)
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(scripts / "prepare-dacte.ps1"),
        ],
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 2
    html = (tmp_path / "runtime/installation/dacte-diagnostic.html").read_text(encoding="utf-8-sig")
    assert "A preparação ainda não foi concluída" in html and "__STYLE__" not in html
    assert 'id="theme"' in html and 'id="report-data"' in html
    data = json.loads(
        (tmp_path / "runtime/installation/dacte-diagnostic.json").read_text(encoding="utf-8-sig")
    )
    assert data["status"] == "pending" and not data["production_ready"]
