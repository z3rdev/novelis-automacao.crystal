from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.crystal_reports.models import DacteRequest
from app.services.crystal_reports.qr_code import (
    QrReference,
    create_qr_bitmap,
    load_qr_reference,
    reference_from_row,
    validate_independent_qr,
)
from app.services.crystal_reports.service import CrystalReportError, CrystalReportService

DOCUMENT = DacteRequest(filial=2, serie="10", documento=10402)
KEY = "35250213254104000255570100000104021000104021"
BASE = "https://example.test/cte/qrCode"
QUERY = f"chCTe={KEY}&tpAmb=1"
REFERENCE = QrReference(KEY, BASE + "?" + QUERY)


@pytest.mark.parametrize("base,query", [
    (BASE, QUERY), (BASE + "?", QUERY), (BASE, "?" + QUERY),
    ("ignored", REFERENCE.payload),
])
def test_complete_or_split_database_url_preserves_parameters(base, query):
    assert reference_from_row(DOCUMENT, ("CTe" + KEY, query, base)) == REFERENCE


@pytest.mark.parametrize("key,query", [
    (KEY, QUERY + " Demo"), (KEY, QUERY.replace(KEY, "1" * 44)),
    ("1" * 44, QUERY), (None, QUERY), (KEY, ""),
    (KEY, QUERY + "&chCTe=" + KEY),
])
def test_missing_mismatched_or_demo_database_data_is_rejected(key, query):
    with pytest.raises(ValueError):
        reference_from_row(DOCUMENT, (key, query, BASE))


def test_independent_bitmap_decodes_to_exact_database_url(tmp_path):
    import zxingcpp
    from PIL import Image

    path = tmp_path / "qr.bmp"
    create_qr_bitmap(REFERENCE, path)
    with Image.open(path) as image:
        symbols = zxingcpp.read_barcodes(image)
    assert [(str(item.format), item.text) for item in symbols] == [("QR Code", REFERENCE.payload)]


@pytest.mark.parametrize("values", [[], [REFERENCE.payload + " Demo"], [REFERENCE.payload, "other"]])
def test_pdf_validation_rejects_every_unexpected_qr(tmp_path, monkeypatch, values):
    monkeypatch.setattr(
        "app.services.crystal_reports.qr_code.read_pdf_symbols",
        lambda path: ([{"format": "QR Code", "value": value} for value in values], ""),
    )
    with pytest.raises(ValueError, match="integralmente"):
        validate_independent_qr(tmp_path / "test.pdf", REFERENCE)


def test_database_query_is_parameterized_and_ambiguous_records_fail(monkeypatch):
    import pyodbc

    closed = []

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def cursor(self):
            return self

        def close(self):
            closed.append(True)

        def execute(self, sql, *parameters):
            assert "TOP (2)" in sql and sql.count("?") == 3
            assert "10402" not in sql
            assert parameters == (2, "10", 10402)
            return self

        def fetchall(self):
            return [(KEY, QUERY, BASE)] * 2

    monkeypatch.setattr(pyodbc, "connect", lambda *args, **kwargs: Connection())
    database = {"server": "test", "database": "test", "auth": "windows"}
    with pytest.raises(ValueError, match="exatamente um"):
        load_qr_reference(database, DOCUMENT)
    assert closed == [True]


def test_database_driver_errors_never_expose_connection_credentials(monkeypatch):
    import pyodbc

    def fail(*args, **kwargs):
        raise pyodbc.Error("PWD=secret-database-password")

    monkeypatch.setattr(pyodbc, "connect", fail)
    with pytest.raises(ValueError) as error:
        load_qr_reference({"server": "test", "database": "test", "auth": "windows"}, DOCUMENT)
    assert "secret-database-password" not in str(error.value)


def test_service_checks_symbols_and_cleans_bitmap_on_failure(tmp_path, monkeypatch):
    class Config:
        def get(self, key, fallback=""):
            return fallback

        def consulta_db(self):
            return dict(server="test", database="test", user="test", **{"pass": "secret"})

    service = CrystalReportService(SimpleNamespace(storage_dir=tmp_path), Config())
    monkeypatch.setattr("app.services.crystal_reports.service.load_qr_reference", lambda *args: REFERENCE)
    seen_images = []

    def export(payload):
        image = Path(payload["qr_image_path"])
        assert image.is_file()
        assert payload["qr_provider"] == "python"
        seen_images.append(image)
        Path(payload["output_path"]).write_bytes(b"%PDF-test-output")

    def reject(path, reference):
        assert reference == REFERENCE
        raise ValueError("QR divergente")

    monkeypatch.setattr(service, "_execute", export)
    monkeypatch.setattr("app.services.crystal_reports.service.validate_independent_qr", reject)
    with pytest.raises(CrystalReportError, match="QR divergente"):
        service.export(DOCUMENT)
    assert seen_images and not seen_images[0].exists()
    assert not list(tmp_path.rglob("*.pdf"))
