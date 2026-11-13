import hashlib
import importlib.util
import json
import struct
from pathlib import Path

import pytest

from app.services.crystal_reports.connection import database_configured, report_database
from app.tools.dacte_components import pe_architecture, register_barcodesoft, verify_installer


def load_packaging_module():
    path = Path(__file__).resolve().parents[2] / "scripts" / "prepare-installer-inputs.py"
    spec = importlib.util.spec_from_file_location("dacte_installer_inputs", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pe_file(tmp_path, machine):
    data = bytearray(70)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 60, 64)
    data[64:68] = b"PE\0\0"
    struct.pack_into("<H", data, 68, machine)
    path = tmp_path / "component.dll"
    path.write_bytes(data)
    return path


@pytest.mark.parametrize("machine,expected", [(0x14C, "x86"), (0x8664, "x64"), (0xAA64, "arm64")])
def test_pe_architecture_is_read_from_header(tmp_path, machine, expected):
    assert pe_architecture(pe_file(tmp_path, machine)) == expected


def test_x64_dll_is_never_registered_by_x86_regsvr32(tmp_path):
    path = pe_file(tmp_path, 0x8664)
    result = register_barcodesoft({"barcodesoft": {"path": str(path), "registered": False}})
    assert result["status"] == "wrong_architecture"


def test_unknown_installer_cannot_execute(tmp_path):
    path = pe_file(tmp_path, 0x14C)
    with pytest.raises(ValueError, match="Hash diferente"):
        verify_installer(path, {"sha256": "0" * 64, "engine": "inno-6"})


def test_factory_configuration_removes_secrets_and_developer_paths():
    module = load_packaging_module()
    raw = (
        "NOVELIS_PASS=secret\nCONSULTA_DB_USER=operator\nCONSULTA_DB_SERVER=private-host\n"
        "CRYSTAL_DB_PASS=other-secret\nSESSION_TOKEN=token\nLEGACY_PROJECT_DIR=C:\\Developer\\project\n"
        "XML_SEFAZ_DOWNLOAD_DIR=\\\\private-server\\share\nAUTO_START_WITH_SERVICE=true\n"
        "BROWSER_WIDTH=1024\nNOVELIS_LOGIN_URL=https://example.test/login\n"
        "NOVELIS_PASSWORD_SELECTOR=#password\n"
        "RODOPAR_BROWSER_ENABLED=true\nPENDENTES_PDF_SOURCE=rodopar\n"
    )
    result = module.factory_environment(raw)
    for value in ("secret", "operator", "private-host", "=token", "Developer", "private-server"):
        assert value not in result
    assert "AUTO_START_WITH_SERVICE=false" in result
    assert "BROWSER_WIDTH=1024" in result
    assert "NOVELIS_LOGIN_URL=https://example.test/login" in result
    assert "NOVELIS_PASSWORD_SELECTOR=#password" in result
    assert "RODOPAR_BROWSER_ENABLED=false" in result
    assert "PENDENTES_PDF_SOURCE=crystal" in result


def test_licensed_package_must_stay_inside_private_directory(tmp_path):
    with pytest.raises(RuntimeError, match="fora do diretorio"):
        load_packaging_module().private_input(tmp_path, "../external.exe")


def test_vendor_without_redistribution_evidence_is_not_packaged(tmp_path):
    module = load_packaging_module()
    (tmp_path / "BACKEND").mkdir()
    (tmp_path / "BACKEND" / ".env.example").write_text("NOVELIS_PASS=secret\n")
    reports = tmp_path / "assets" / "reports"
    reports.mkdir(parents=True)
    (reports / "dacte.rpt").write_bytes(b"test-report")
    manifest = {
        "sha256": hashlib.sha256(b"test-report").hexdigest(),
        "stored_credentials": False,
        "has_saved_data": False,
        "fiscal_validation": {"status": "pending"},
    }
    (reports / "dacte.manifest.json").write_text(json.dumps(manifest))
    catalog = tmp_path / "installer" / "dacte"
    catalog.mkdir(parents=True)
    (catalog / "dependencies.json").write_text(
        json.dumps(
            {
                "components": [
                    {"id": "commercial", "redistribution_approved": False, "filename": "setup.exe"}
                ]
            }
        )
    )
    result = module.prepare(tmp_path)
    assert result["included_vendor_components"] == []
    assert result["assisted_components"] == ["commercial"]
    assert not list((tmp_path / "runtime" / "installer-inputs" / "dacte-vendor").iterdir())
    assert (
        "secret"
        not in (tmp_path / "runtime" / "installer-inputs" / "BACKEND.env.example").read_text()
    )


class Config:
    def __init__(self, values):
        self.values = values

    def get(self, key, fallback=""):
        return self.values.get(key, fallback)

    def consulta_db(self):
        return {"server": "fallback", "database": "data", "user": "fallback-user", "pass": "secret"}


def test_windows_authentication_does_not_forward_sql_credentials():
    result = report_database(Config({"CRYSTAL_DB_AUTH": "windows"}))
    assert database_configured(result)
    assert result["user"] == result["password"] == ""


def test_report_server_instance_and_port_are_external_configuration():
    config = Config(
        {
            "CRYSTAL_DB_HOST": "report-host",
            "CRYSTAL_DB_INSTANCE": "REPORTS",
            "CRYSTAL_DB_PORT": "28006",
        }
    )
    assert report_database(config)["server"] == "report-host\\REPORTS,28006"


def test_invalid_database_port_is_rejected():
    with pytest.raises(ValueError):
        report_database(Config({"CRYSTAL_DB_HOST": "host", "CRYSTAL_DB_PORT": "70000"}))
