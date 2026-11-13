from types import SimpleNamespace

import pytest

from app.services.crystal_reports.qr_code import QrReference, validate_independent_qr
from app.services.crystal_reports.validation import _read_page_symbols

KEY = "21260813254104001146570100000003971000003972"
URL = "https://example.test/cte?chCTe=" + KEY + "&tpAmb=1"


def symbol(format, value, valid=True):
    return SimpleNamespace(format=format, text=value, valid=valid)


class PageStub:
    def __init__(self):
        self.scales = []
        self.closed = []

    def render(self, scale):
        self.scales.append(scale)
        return SimpleNamespace(to_pil=lambda: scale, close=lambda: self.closed.append(scale))


def test_checksum_error_at_216_dpi_retries_and_reads_exact_key_at_288_dpi(monkeypatch):
    import zxingcpp

    page = PageStub()

    def decode(scale, **kwargs):
        assert kwargs["return_errors"] is True
        barcode = symbol("Code 128", "90" + KEY[2:], False) if scale == 3 else symbol("Code 128", KEY)
        return [symbol("QR Code", URL), barcode]

    monkeypatch.setattr(zxingcpp, "read_barcodes", decode)
    result = _read_page_symbols(page)
    assert result == [{"format": "QR Code", "value": URL}, {"format": "Code 128", "value": KEY}]
    assert page.scales == page.closed == [3, 4]


def test_successful_first_read_does_not_render_again(monkeypatch):
    import zxingcpp

    page = PageStub()
    monkeypatch.setattr(zxingcpp, "read_barcodes", lambda *a, **kw: [
        symbol("QR Code", URL), symbol("Code 128", KEY)
    ])
    assert len(_read_page_symbols(page)) == 2
    assert page.scales == page.closed == [3]


def test_retries_are_bounded_and_invalid_barcodes_are_never_accepted(monkeypatch):
    import zxingcpp

    page = PageStub()
    monkeypatch.setattr(zxingcpp, "read_barcodes", lambda *a, **kw: [
        symbol("QR Code", URL), symbol("Code 128", KEY, False)
    ])
    assert _read_page_symbols(page) == [{"format": "QR Code", "value": URL}]
    assert page.scales == page.closed == [3, 4, 6]


def test_real_mismatch_still_blocks_the_pdf(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.crystal_reports.qr_code.read_pdf_symbols", lambda path: ([
        {"format": "QR Code", "value": URL},
        {"format": "Code 128", "value": "90" + KEY[2:]},
    ], ""))
    with pytest.raises(ValueError, match="chave consultada"):
        validate_independent_qr(tmp_path / "test.pdf", QrReference(KEY, URL))
