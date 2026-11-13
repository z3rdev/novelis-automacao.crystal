"""Import a stable RPT snapshot, remove stored connections, and verify preservation."""
import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "BACKEND"))

from app.config.legacy_config import LegacyConfig
from app.config.settings import Settings
from app.services.crystal_reports.service import CrystalReportService


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def import_report(source: Path) -> dict:
    content = source.read_bytes()
    source_hash = digest(content)
    if source_hash != digest(source.read_bytes()):
        raise RuntimeError("O relatorio mudou durante a leitura. Salve-o e repita a importacao.")
    backup = ROOT / "runtime" / "rpt-source-originals" / (source_hash + ".rpt")
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_bytes(content)
    settings = Settings(_env_file=None)
    config = LegacyConfig(settings)
    config.values["CRYSTAL_DACTE_RPT_PATH"] = str(backup)
    service = CrystalReportService(settings, config)
    original = service.inspect()
    original_audit = service._execute({"action": "audit"})
    failures = [f["name"] for r in original_audit["reports"] for f in r["formulas"] if not f["compiled"]]
    if failures:
        raise RuntimeError("Formulas que nao compilaram: " + ", ".join(failures))
    if any(fn.lower().startswith("rod") for r in original["external_function_references"] for fn in r["functions"]):
        raise RuntimeError("O RPT ainda referencia funcoes externas do Rodopar.")
    candidate = ROOT / "runtime" / "dacte-packaging" / (source_hash + ".rpt")
    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate.unlink(missing_ok=True)
    service._execute({"action": "package", "output_path": str(candidate)})
    config.values["CRYSTAL_DACTE_RPT_PATH"] = str(candidate)
    packaged = service.inspect()
    audit = service._execute({"action": "audit"})
    assert not packaged["has_saved_data"], "O RPT empacotado ainda contem dados salvos."
    assert original["report"] == packaged["report"], "Metadados/formulas do relatorio principal mudaram."
    assert original["subreports"] == packaged["subreports"], "Subrelatorios mudaram."
    for before, after in zip(original_audit["reports"], audit["reports"], strict=True):
        assert before["fields"] == after["fields"], "A geometria ou as fontes do layout mudaram."
        assert not after["credential_fields"], "O RPT ainda armazena credenciais."
    assets = ROOT / "assets" / "reports"
    assets.mkdir(parents=True, exist_ok=True)
    target = assets / "dacte.rpt"
    shutil.copyfile(candidate, target)
    fonts = sorted({f["font"] for r in audit["reports"] for f in r["fields"]})
    warnings = []
    for report in audit["reports"]:
        for field in report["fields"]:
            if field["field"].lower() == "{@f_cobbar2}" and "128" not in field["font"]:
                warnings.append({"field": field["object"], "issue": "contingency_barcode_font",
                                 "message": "Formula codificada Code 128 usa fonte " + field["font"]})
    manifest = {
        "schema_version": 1, "file": "dacte.rpt", "source_filename": source.name,
        "source_sha256": source_hash, "sha256": digest(target.read_bytes()),
        "packaged_at": datetime.now(timezone.utc).isoformat(),
        "has_saved_data": False, "stored_credentials": False,
        "formulas_preserved": True, "layout_preserved": True, "formulas_compiled": True,
        "required_fonts": fonts, "demo_fonts": [f for f in fonts if "DEMO" in f.upper()],
        "external_function_references": original["external_function_references"],
        "parameters": original["report"]["parameters"], "warnings": warnings,
        "fiscal_validation": {"status": "pending", "reason": "Exige documentos de referencia, incluindo contingencia."},
    }
    (assets / "dacte.manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    result = import_report(args.source)
    print(json.dumps({"sha256": result["sha256"], "required_fonts": result["required_fonts"],
                      "warnings": result["warnings"], "fiscal_validation": result["fiscal_validation"]}, ensure_ascii=True))
