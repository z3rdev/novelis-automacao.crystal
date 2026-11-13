"""Decode rendered PDF symbols against an archived CT-e XML, without changing formulas."""

import hashlib
from pathlib import Path
from xml.etree import ElementTree


def read_pdf_symbols(pdf_path: Path, output_dir: Path | None = None) -> tuple[list[dict], str]:
    import pypdfium2
    from pypdf import PdfReader

    decoded = []
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
    with pypdfium2.PdfDocument(pdf_path) as document:
        for index in range(len(document)):
            page = document[index]
            try:
                decoded.extend(_read_page_symbols(
                    page, output_dir / f"page-{index + 1}.png" if output_dir else None
                ))
            finally:
                page.close()
    texts = "\n".join(page.extract_text() or "" for page in PdfReader(pdf_path).pages)
    return decoded, texts


def _read_page_symbols(page, output_path: Path | None = None) -> list[dict]:
    import zxingcpp

    decoded = {}
    # Thin Code 128 bars can alias at 216 dpi, even in a correct vector PDF.
    # Retry at 288/432 dpi only when a required symbol type is still unreadable.
    for scale in (3, 4, 6):
        bitmap = page.render(scale=scale)
        try:
            image = bitmap.to_pil()
            for symbol in zxingcpp.read_barcodes(image, return_errors=True):
                if not symbol.valid:
                    continue  # A partial decode/checksum error is never evidence.
                identity = (str(symbol.format), symbol.text.strip())
                decoded[identity] = {"format": identity[0], "value": identity[1]}
            complete = {"QR Code", "Code 128"}.issubset({key[0] for key in decoded})
            if output_path and (complete or scale == 6):
                image.save(output_path)
        finally:
            bitmap.close()
        if complete:
            break
    return list(decoded.values())


def validate_pdf_codes(pdf_path: Path, xml_path: Path, output_dir: Path) -> dict:
    content = xml_path.read_bytes()
    if (
        len(content) > 10 * 1024 * 1024
        or b"<!DOCTYPE" in content.upper()
        or b"<!ENTITY" in content.upper()
    ):
        raise ValueError("XML de referencia nao permitido.")
    ns = {"cte": "http://www.portalfiscal.inf.br/cte"}
    xml = ElementTree.fromstring(content)
    info = xml.find(".//cte:infCte", ns)
    if info is None:
        raise ValueError("XML de referencia nao contem infCte.")
    key = info.get("Id", "").removeprefix("CTe")
    qr = xml.findtext(".//cte:qrCodCTe", default="", namespaces=ns).strip()
    if len(key) != 44 or not key.isdecimal() or not qr:
        raise ValueError("Referencia precisa conter chave de 44 digitos e QR Code.")
    decoded, texts = read_pdf_symbols(pdf_path, output_dir)
    protocol = xml.findtext(".//cte:protCTe/cte:infProt/cte:nProt", default="", namespaces=ns)
    checks = {
        "access_key_barcode_matches": any(
            x["format"] == "Code 128" and x["value"] == key for x in decoded
        ),
        "qr_matches": any(x["format"] == "QR Code" and x["value"] == qr for x in decoded),
        "protocol_present": bool(protocol and protocol in texts),
    }
    emission = info.findtext("cte:ide/cte:tpEmis", default="", namespaces=ns)
    demo_qr = any(
        x["format"] == "QR Code" and x["value"] == qr + " Demo" for x in decoded
    )
    return {
        "status": "ok" if all(checks.values()) else "failed",
        "checks": checks,
        "decoded_formats": sorted({x["format"] for x in decoded}),
        "decoded_symbols": decoded,
        "reference_sha256": hashlib.sha256(content).hexdigest(),
        "emission_type": emission,
        "demo_qr_suffix_detected": demo_qr,
        "fiscal_equivalence": "pending",
        "note": "A leitura dos simbolos nao valida assinatura, situacao atual ou regra de contingencia.",
    }
