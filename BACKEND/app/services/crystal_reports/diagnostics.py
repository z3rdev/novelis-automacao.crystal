import hashlib
import json
from datetime import UTC, datetime
from importlib.util import find_spec
from pathlib import Path

from app.services.crystal_reports.code128 import encoder_available
from app.services.crystal_reports.connection import check_database, report_database
from app.services.crystal_reports.models import DacteRequest
from app.services.crystal_reports.service import CrystalReportError, CrystalReportService
from app.services.crystal_reports.validation import validate_pdf_codes


def diagnose(
    service: CrystalReportService,
    connect: bool = False,
    document: DacteRequest | None = None,
    xml_reference: Path | None = None,
) -> dict:
    report = {
        "schema_version": 1,
        "checked_at": datetime.now(UTC).isoformat(),
        "status": "pending",
        "checks": {},
        "fiscal_validation": "pending",
        "production_ready": False,
    }
    checks = report["checks"]
    try:
        environment = service._execute({"action": "environment"})["environment"]
        checks["environment"] = environment
    except CrystalReportError as exc:
        checks["environment"] = {"error": str(exc), "compatible": False}
        return report
    path = service.report_path
    manifest_path = path.with_suffix(".manifest.json")
    if not path.is_file():
        checks["report"] = {"status": "missing", "message": "RPT integrado nao encontrado."}
        return report
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    )
    actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    checks["integrity"] = {
        "status": "ok" if manifest.get("sha256") == actual_hash else "unverified",
        "sha256": actual_hash,
    }
    checks["fiscal_baseline"] = manifest.get("fiscal_validation", {"status": "pending"})
    checks["layout_warnings"] = manifest.get("warnings", [])
    pdf_engine = service.config.get("CRYSTAL_PDF_ENGINE", "windows").lower()
    qr_provider = service.config.get("CRYSTAL_QR_PROVIDER", "python").lower()
    independent_qr = qr_provider == "python"
    code128_provider = service.config.get("CRYSTAL_CODE128_PROVIDER", qr_provider).lower()
    independent_code128 = code128_provider == "python"
    checks["qr_renderer"] = {
        "provider": qr_provider,
        "status": "ok" if (
            (independent_qr and find_spec("qrcode") and find_spec("PIL"))
            or (qr_provider == "report" and environment["bcs_functions"]["available"])
        ) else "missing",
        "barcodesoft_required": not independent_qr,
    }
    checks["pdf_output"] = {
        "engine": pdf_engine,
        "windows_printer_available": environment.get("windows_pdf_printer_available", False),
    }
    checks["code128_renderer"] = {
        "provider": code128_provider,
        "status": "ok" if ((independent_code128 and encoder_available()) or code128_provider == "report") else "missing",
        "barcode_font_required": not independent_code128,
    }
    required_fonts = [
        font for font in manifest.get("required_fonts", [])
        if (not independent_qr or "bcsqrcode" not in font.casefold())
        and (not independent_code128 or "128" not in font.casefold())
    ]
    available_fonts = {f.casefold() for f in environment["fonts"]}
    missing_fonts = [f for f in required_fonts if f.casefold() not in available_fonts]
    checks["fonts"] = {
        "status": "missing" if missing_fonts else "ok",
        "required": required_fonts,
        "missing": missing_fonts,
        "demo": [f for f in required_fonts if "DEMO" in f.upper()],
    }
    if environment["compatible"]:
        try:
            audit = service._execute({"action": "audit"})
            failures = [f for r in audit["reports"] for f in r["formulas"] if not f["compiled"]]
            stored = sum(len(r["credential_fields"]) for r in audit["reports"])
            checks["report"] = {
                "status": "ok" if not failures and not stored else "failed",
                "failed_formulas": failures,
                "stored_credentials": bool(stored),
            }
        except CrystalReportError as exc:
            checks["report"] = {"status": "failed", "message": str(exc)}
    try:
        database = report_database(service.config)
        checks["database"] = (
            check_database(database, document) if connect else {"status": "not_tested"}
        )
    except ValueError as exc:
        checks["database"] = {"status": "error", "message": str(exc)}
    checks["export"] = {
        "status": "not_tested",
        "message": "Informe filial, serie e documento para testar exportacao.",
    }
    checks["symbols"] = {
        "status": "not_tested",
        "message": "Informe tambem um XML de referencia para comparar os codigos.",
    }
    if document:
        try:
            output = service.export(document)
            checks["export"] = {"status": "ok", "pdf": str(output)}
            if xml_reference:
                checks["symbols"] = validate_pdf_codes(
                    output,
                    xml_reference,
                    service.settings.storage_dir / "installation" / "pdf-validation",
                )
            else:
                checks["symbols"] = {
                    "status": "pending",
                    "message": "Informe XML de referencia para ler e comparar os codigos.",
                }
        except (CrystalReportError, ValueError, ImportError, OSError) as exc:
            checks["export"] = {"status": "failed", "message": str(exc)}
            checks["symbols"] = {
                "status": "not_tested",
                "message": "A exportacao falhou; nenhum PDF foi validado.",
            }
    technical_ok = (
        environment["compatible"]
        and checks["qr_renderer"]["status"] == "ok"
        and checks["code128_renderer"]["status"] == "ok"
        and all(x["loadable"] for x in environment["native_dlls"])
        and not missing_fonts
        and checks.get("report", {}).get("status") == "ok"
        and checks["integrity"]["status"] == "ok"
        and (pdf_engine == "native" or (pdf_engine == "windows" and environment.get("windows_pdf_printer_available", False)))
    )
    report["dependencies_ready"] = technical_ok
    requested_checks_ok = (
        (not connect or checks["database"]["status"] == "ok")
        and (not document or checks["export"]["status"] == "ok")
        and (not xml_reference or checks["symbols"]["status"] == "ok")
    )
    report["status"] = "technical_ready" if technical_ok and requested_checks_ok else "pending"
    return report


def write_diagnostic(report: dict, directory: Path) -> None:
    from html import escape

    directory.mkdir(parents=True, exist_ok=True)
    data = json.dumps(report, ensure_ascii=False, indent=2)
    (directory / "dacte-diagnostic.json").write_text(data + "\n", encoding="utf-8")
    html = (
        "<!doctype html><html lang='pt-BR'><meta charset='utf-8'><title>Diagnostico DACTE</title>"
        "<style>body{font:16px system-ui;max-width:1100px;margin:40px auto;padding:20px}"
        "pre{white-space:pre-wrap;background:#f2f4f7;padding:20px}</style>"
        "<h1>Diagnostico de instalacao DACTE</h1><p>Prontidao tecnica e validacao fiscal sao verificacoes distintas.</p>"
        "<pre>" + escape(data) + "</pre></html>"
    )
    (directory / "dacte-diagnostic.html").write_text(html, encoding="utf-8")
