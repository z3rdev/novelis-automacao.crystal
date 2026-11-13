import argparse
import json
import os
from pathlib import Path

from app.config.legacy_config import LegacyConfig
from app.config.settings import Settings
from app.services.crystal_reports.diagnostics import diagnose, write_diagnostic
from app.services.crystal_reports.models import DacteRequest
from app.services.crystal_reports.service import CrystalReportService
from app.tools.dacte_components import prepare_components, register_barcodesoft
from app.tools.dacte_fonts import repair_qr_font


def main() -> int:
    parser = argparse.ArgumentParser(description="Preparacao e diagnostico integrado DACTE")
    parser.add_argument("--repair", action="store_true")
    parser.add_argument("--assist", action="store_true")
    parser.add_argument("--silent", action="store_true")
    parser.add_argument("--inputs", type=Path)
    parser.add_argument("--filial", type=int)
    parser.add_argument("--serie")
    parser.add_argument("--documento", type=int)
    parser.add_argument("--xml-reference", type=Path)
    parser.add_argument("--no-database", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    root = settings.backend_root.parent
    service = CrystalReportService(settings, LegacyConfig(settings))
    directory = root / "runtime" / "installation"
    inputs = json.loads(args.inputs.read_text(encoding="utf-8-sig")) if args.inputs else {}
    changes = []
    if args.repair:
        environment = service._execute({"action": "environment"})["environment"]
        qr_provider = service.config.get("CRYSTAL_QR_PROVIDER", "python").lower()
        code128_provider = service.config.get("CRYSTAL_CODE128_PROVIDER", qr_provider).lower()
        changes = prepare_components(
            root, environment, inputs, args.assist, args.silent, qr_provider=qr_provider,
            code128_provider=code128_provider,
        )
        if qr_provider == "report":
            environment = service._execute({"action": "environment"})["environment"]
            changes.append(
                {"component": "barcodesoft_registration", **register_barcodesoft(environment)}
            )
            changes.append({"component": "qr_font_registration", **repair_qr_font()})
    provided = [args.filial is not None, bool(args.serie), args.documento is not None]
    if any(provided) and not all(provided):
        parser.error("Informe filial, serie e documento juntos.")
    document = (
        DacteRequest(filial=args.filial, serie=args.serie, documento=args.documento)
        if all(provided)
        else None
    )
    report = diagnose(
        service, connect=not args.no_database, document=document, xml_reference=args.xml_reference
    )
    report["preparation"] = changes
    if any(
        change.get("status") not in {
            "already_present", "already_registered", "registered", "installed", "not_required"
        }
        for change in changes
    ):
        report["status"] = "pending"
    report["platform"] = {
        "os": os.name,
        "host_bits": 64 if os.environ.get("ProgramFiles(x86)") else 32,
    }
    write_diagnostic(report, directory)
    print(
        json.dumps(
            {
                "status": report["status"],
                "production_ready": report.get("production_ready", False),
                "report": str(directory / "dacte-diagnostic.html"),
            },
            ensure_ascii=True,
        )
    )
    if any(x.get("status") == "needs_admin" for x in changes):
        return 3
    return 0 if report["status"] == "technical_ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
