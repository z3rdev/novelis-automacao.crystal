"""Generate local candidates and retain evidence outside the publication tree."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "BACKEND"))

from app.config.legacy_config import LegacyConfig
from app.config.settings import Settings
from app.services.crystal_reports.models import DacteRequest
from app.services.rpt_rs.comparison import compare
from app.services.rpt_rs.service import RptRsService


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document", action="append", required=True, metavar="FILIAL-SERIE-NUMERO")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "runtime/rpt-rs-evaluation")
    parser.add_argument("--reference-dir", type=Path)
    parser.add_argument("--worker", type=Path)
    arguments = parser.parse_args()
    settings = Settings(storage_dir=arguments.output_dir.resolve())
    config = LegacyConfig(settings)
    if arguments.worker:
        config.values["RPT_RS_WORKER_PATH"] = str(arguments.worker.resolve())
    service = RptRsService(settings, config)
    results = []
    for label in arguments.document:
        parts = label.split("-")
        if len(parts) != 3 or not all(part.isdecimal() for part in parts):
            parser.error("Documento deve seguir FILIAL-SERIE-NUMERO com valores numericos.")
        document = DacteRequest(filial=int(parts[0]), serie=parts[1], documento=int(parts[2]))
        item = {"document": label, "status": "failed", "production_ready": False}
        try:
            output = service.export_candidate(document)
            evidence = json.loads(output.with_suffix(".json").read_text(encoding="utf-8"))
            item.update(candidate=str(output), symbols_match_database=evidence["symbols_match_database"],
                        pages=evidence["render"]["pages"], adaptation=evidence["adaptation"],
                        datasets=evidence["datasets"], diagnostics=evidence["render"]["diagnostics"])
            item["status"] = "candidate_generated" if item["symbols_match_database"] else "symbols_failed"
            if arguments.reference_dir:
                reference = arguments.reference_dir / f"candidate-dacte-{label}-windows.pdf"
                item["comparison"] = compare(output, reference, retain_text=True)
                output.with_suffix(".comparison.json").write_text(
                    json.dumps(item["comparison"], indent=2, ensure_ascii=False), encoding="utf-8")
                item["status"] = "review_required"
                comparison = item["comparison"]
                if (not item["symbols_match_database"] or not comparison["pagination_matches"]
                        or comparison["reference_tokens_missing"] or not comparison["decoded_symbols_match_reference"]):
                    item["status"] = "incompatible_reference"
        except (RuntimeError, ValueError, OSError) as error:
            item["error_type"] = type(error).__name__
            item["error"] = str(error)
        results.append(item)
        # Console output contains only status/counts. Local JSON retains the fiscal comparison.
        print(json.dumps({key: item[key] for key in ("document", "status", "pages", "symbols_match_database", "error_type")
                          if key in item}), flush=True)
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    (arguments.output_dir / "evaluation.json").write_text(
        json.dumps({"results": results, "production_ready": False}, indent=2, ensure_ascii=False), encoding="utf-8")
    return 2 if any(item["status"] in {"failed", "symbols_failed", "incompatible_reference"}
                    for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
