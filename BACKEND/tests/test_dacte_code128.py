import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.crystal_reports.code128 import create_code128_bitmap, validate_code128
from app.services.crystal_reports.diagnostics import diagnose
from app.services.crystal_reports.models import DacteRequest
from app.services.crystal_reports.qr_code import QrReference
from app.services.crystal_reports.service import CrystalReportError, CrystalReportService
from app.tools.dacte_components import prepare_components

KEY = "35250213254104000255570100000104021000104021"
REFERENCE = QrReference(KEY, f"https://example.test/cte?chCTe={KEY}&tpAmb=1")


def test_bitmap_decodes_exactly_without_any_font(tmp_path):
    import zxingcpp
    from PIL import Image

    path = tmp_path / "code128.bmp"
    create_code128_bitmap(KEY, path)
    with Image.open(path) as image:
        assert image.format == "BMP" and image.mode == "RGB"
        symbols = zxingcpp.read_barcodes(image)
        assert [(str(item.format), item.text) for item in symbols if item.valid] == [("Code 128", KEY)]
        # A 44-digit Code 128 C uses 277 modules plus ten quiet modules on each side.
        assert image.width == 297 * 4
        assert all(image.getpixel((x, image.height // 2)) == (255, 255, 255) for x in range(40))


@pytest.mark.parametrize("key", ["1" * 43, "1" * 45, "CTe" + KEY, "A" + KEY[1:], "١" * 44])
def test_encoder_rejects_invalid_access_keys(tmp_path, key):
    with pytest.raises(ValueError, match="44 digitos"):
        create_code128_bitmap(key, tmp_path / "invalid.bmp")


def test_missing_and_mismatched_barcodes_are_distinguished():
    with pytest.raises(ValueError, match="ausente ou ilegivel"):
        validate_code128([{"format": "QR Code", "value": REFERENCE.payload}], KEY)
    with pytest.raises(ValueError, match="nao corresponde"):
        validate_code128([{"format": "Code 128", "value": "0" * 44}], KEY)
    validate_code128([{"format": "Code 128", "value": KEY}], KEY)


def test_service_supplies_both_bitmaps_and_cleans_temporary_files(tmp_path, monkeypatch):
    config = SimpleNamespace(get=lambda _key, default="": default,
                             consulta_db=lambda: {"server": "test", "database": "test",
                                                 "user": "test", "pass": "secret"})
    service = CrystalReportService(SimpleNamespace(storage_dir=tmp_path), config)
    monkeypatch.setattr("app.services.crystal_reports.service.load_qr_reference", lambda *_args: REFERENCE)
    seen = []

    def execute(payload):
        assert payload["code128_provider"] == payload["qr_provider"] == "python"
        for name in ("code128_image_path", "qr_image_path"):
            path = Path(payload[name])
            assert path.is_file()
            seen.append(path)
        Path(payload["output_path"]).write_bytes(b"%PDF-test-output")

    monkeypatch.setattr(service, "_execute", execute)
    monkeypatch.setattr("app.services.crystal_reports.service.validate_independent_qr", lambda *_args: None)
    output = service.export(DacteRequest(filial=2, serie="10", documento=10402))
    assert output.is_file() and len(seen) == 2
    assert all(not path.exists() for path in seen)


def test_rejected_pdf_is_removed_after_code128_validation(tmp_path, monkeypatch):
    config = SimpleNamespace(get=lambda _key, default="": default,
                             consulta_db=lambda: {"server": "test", "database": "test",
                                                 "user": "test", "pass": "secret"})
    service = CrystalReportService(SimpleNamespace(storage_dir=tmp_path), config)
    monkeypatch.setattr("app.services.crystal_reports.service.load_qr_reference", lambda *_args: REFERENCE)
    monkeypatch.setattr(service, "_execute", lambda payload: Path(payload["output_path"]).write_bytes(b"%PDF-test"))

    def reject(*_args):
        validate_code128([], KEY)

    monkeypatch.setattr("app.services.crystal_reports.service.validate_independent_qr", reject)
    with pytest.raises(CrystalReportError, match="Code 128 ausente ou ilegivel"):
        service.export(DacteRequest(filial=2, serie="10", documento=10402))
    assert not list(tmp_path.rglob("*.pdf"))
    assert not list(tmp_path.rglob("*.bmp"))


def test_independent_code128_does_not_request_a_commercial_font_installer(tmp_path):
    folder = tmp_path / "installer/dacte"
    folder.mkdir(parents=True)
    (folder / "dependencies.json").write_text(json.dumps({"components": [
        {"id": "code128", "redistribution_approved": False}]}))
    result = prepare_components(tmp_path, {"fonts": []}, {}, assist=False,
                                qr_provider="python", code128_provider="python")
    assert result == [{"component": "code128", "status": "not_required"}]


@pytest.mark.parametrize("provider,missing", [("python", []), ("report", ["IDAutomationSC128L DEMO"])])
def test_font_diagnostics_follow_the_selected_code128_provider(tmp_path, provider, missing):
    import hashlib

    path = tmp_path / "dacte.rpt"
    path.write_bytes(b"test-report")
    path.with_suffix(".manifest.json").write_text(json.dumps({
        "sha256": hashlib.sha256(b"test-report").hexdigest(),
        "required_fonts": ["IDAutomationSC128L DEMO"]}))
    config = SimpleNamespace(get=lambda key, default="": provider if key == "CRYSTAL_CODE128_PROVIDER" else default,
                             consulta_db=dict)

    def execute(payload):
        if payload["action"] == "environment":
            return {"environment": {"compatible": True, "fonts": [], "bcs_functions": {"available": False},
                                    "native_dlls": [{"loadable": True}], "windows_pdf_printer_available": True}}
        return {"reports": [{"formulas": [], "credential_fields": []}]}

    report = diagnose(SimpleNamespace(report_path=path, config=config, _execute=execute))
    assert report["checks"]["fonts"]["missing"] == missing
    assert report["dependencies_ready"] is (provider == "python")
