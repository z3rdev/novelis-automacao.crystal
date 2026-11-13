"""Independent QR renderer using the original database payload, never vendor output."""

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from app.automation.cancellation import cancellable_cursor
from app.services.crystal_reports.code128 import validate_code128
from app.services.crystal_reports.connection import odbc_connection_string
from app.services.crystal_reports.models import DacteRequest
from app.services.crystal_reports.validation import read_pdf_symbols


@dataclass(frozen=True)
class QrReference:
    access_key: str
    payload: str


def reference_from_row(document: DacteRequest, row) -> QrReference:
    key_match = re.fullmatch(r"(?:CTe)?([0-9]{44})", str(row[0] or "").strip())
    if not key_match:
        raise ValueError("CTE_ID do banco nao contem uma chave CT-e de 44 digitos.")
    key = key_match[1]
    if (
        key[20:22] != "57"
        or not document.serie.isdecimal()
        or int(key[22:25]) != int(document.serie)
        or int(key[25:34]) != document.documento
    ):
        raise ValueError("A chave do banco nao corresponde ao CT-e solicitado.")
    qr_value, base_url = str(row[1] or ""), str(row[2] or "")
    # Keep complete URLs verbatim. Some database rows split the URL and query
    # without storing '?'; supply only that separator, never fiscal parameters.
    if "http" in qr_value.lower():
        payload = qr_value
    else:
        separator = "" if base_url.endswith(("?", "&")) else ("&" if "?" in base_url else "?")
        payload = base_url + separator + qr_value.lstrip("?&")
    parsed = urlsplit(payload)
    if (
        not qr_value
        or len(payload) > 4096
        or any(character.isspace() for character in payload)
        or parsed.scheme.lower() not in {"http", "https"}
        or not parsed.hostname
        or parse_qs(parsed.query).get("chCTe") != [key]
    ):
        raise ValueError("CTEQRC/CTEURL do banco nao fornecem um QR valido para esta chave.")
    return QrReference(key, payload)


def load_qr_reference(database: dict, document: DacteRequest) -> QrReference:
    import pyodbc

    try:
        connection = pyodbc.connect(odbc_connection_string(database), timeout=10)
        try:
            connection.timeout = 15
            with cancellable_cursor(connection.cursor()) as cursor:
                rows = cursor.execute(
                    "SELECT TOP (2) c.CTE_ID, c.CTEQRC, f.CTEURL "
                    "FROM RODCON c LEFT JOIN RODFIL f ON f.CODFIL=c.CODFIL "
                    "WHERE c.CODFIL=? AND c.SERCON=? AND c.CODCON=? AND c.SITUAC <> 'I'",
                    document.filial, document.serie, document.documento,
                ).fetchall()
        finally:
            connection.close()
    except (pyodbc.Error, OSError):
        # Driver errors can contain connection credentials; never expose them.
        raise ValueError("Nao foi possivel consultar os dados originais do QR no banco.") from None
    if len(rows) != 1:
        raise ValueError("Consulta do QR precisa retornar exatamente um CT-e ativo.")
    return reference_from_row(document, rows[0])


def create_qr_bitmap(reference: QrReference, path: Path) -> None:
    import qrcode

    # F_QRCODE used Barcodesoft's level 2, which is ISO QR level L.
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=8, border=4)
    qr.add_data(reference.payload, optimize=0)
    try:
        qr.make(fit=True)
    except qrcode.exceptions.DataOverflowError:
        raise ValueError("Conteudo do banco excede a capacidade do QR Code.") from None
    # Legacy Crystal supports BMP without relying on an external barcode font/UFL.
    qr.make_image(fill_color="black", back_color="white").convert("RGB").save(path, format="BMP")


def validate_independent_qr(pdf_path: Path, reference: QrReference) -> None:
    symbols, _ = read_pdf_symbols(pdf_path)
    qr_values = [item["value"] for item in symbols if item["format"] == "QR Code"]
    if not qr_values or any(value != reference.payload for value in qr_values):
        raise ValueError("QR do PDF nao corresponde integralmente ao conteudo original do banco.")
    validate_code128(symbols, reference.access_key)
