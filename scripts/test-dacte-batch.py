"""Test a list through the real Crystal PDF stage, writing only local test evidence."""

import argparse
import asyncio
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "BACKEND"))

from app.automation.flows.pendentes.controles.crystal_pdf import CrystalPdfRunner
from app.config.legacy_config import LegacyConfig
from app.config.settings import Settings
from app.domain.models import RunStartRequest
from app.services.crystal_reports.models import DacteRequest


class NoBrowser:
    def __getattr__(self, name):
        raise AssertionError("Este teste nao pode utilizar navegador: " + name)


def parse_documents(raw: str) -> dict[str, DacteRequest]:
    documents = {}
    uncommented = "\n".join(line.split("#", 1)[0] for line in raw.splitlines())
    for value in re.split(r"[\s,;]+", uncommented.strip()):
        if not value:
            continue
        match = re.fullmatch(r"([0-9]+)-([0-9A-Za-z]+)-([0-9]+)", value)
        if not match:
            raise ValueError(f"CT-e invalido: {value}. Use filial-serie-numero.")
        document = DacteRequest(filial=int(match[1]), serie=match[2], documento=int(match[3]))
        key = f"{document.filial}-{document.serie}-{document.documento}"
        documents[key] = document
    if not documents:
        raise ValueError("A lista de CT-es esta vazia.")
    return documents


def combine_pdfs(results: list[dict], directory: Path) -> Path | None:
    from pypdf import PdfWriter

    successful = [item for item in results if item["status"] == "ok"]
    if not successful:
        return None
    output = directory / "dactes-lote-teste.pdf"
    with PdfWriter() as writer:
        for item in successful:
            writer.append(item["pdf"])
        with output.open("wb") as stream:
            writer.write(stream)
    return output


async def run_batch(documents: dict[str, DacteRequest]) -> int:
    from pypdf import PdfReader

    batch_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%SZ") + "-" + uuid4().hex[:8]
    directory = ROOT / "runtime" / "output" / "dacte-batches" / batch_id
    directory.mkdir(parents=True)
    events, results, started = [], {}, {}
    total_start = perf_counter()

    async def emit(message, **event):
        events.append({"message": message, **event})
        kind, payload = event.get("kind"), event.get("payload", {})
        cte = payload.get("cte")
        if kind == "crystal_pdf.progress":
            started[cte] = perf_counter()
            print(message, flush=True)
        elif kind in {"crystal_pdf.saved", "crystal_pdf.error"}:
            elapsed = round(perf_counter() - started[cte], 2)
            if kind == "crystal_pdf.saved":
                path = Path(payload["pdfFile"])
                results[cte] = {"cte": cte, "status": "ok", "seconds": elapsed,
                                "pages": len(PdfReader(path).pages), "pdf": str(path)}
                print(f"OK {cte}: {elapsed}s", flush=True)
            else:
                results[cte] = {"cte": cte, "status": "failed", "seconds": elapsed,
                                "error": payload.get("error")}
                print(f"FALHA {cte}: {payload.get('error')}", flush=True)

    settings = Settings()
    config = LegacyConfig(settings)
    runner = CrystalPdfRunner(settings, config, emit)
    plan = {
        "faltandoPdf": list(documents),
        "checked": [{"cte": key, "row": document.model_dump()} for key, document in documents.items()],
    }
    failure = ""
    try:
        await runner.run(
            NoBrowser(), {"downloadTargetDir": str(directory / "individuais")}, plan,
            RunStartRequest(flow="pendentes", dry_run=False), batch_id, {"stopOnError": False},
        )
    except (RuntimeError, ValueError, OSError, ImportError) as exc:
        failure = str(exc)
    ordered = [results.get(key, {"cte": key, "status": "not_generated"}) for key in documents]
    combined = combine_pdfs(ordered, directory)
    successful = sum(item["status"] == "ok" for item in ordered)
    report = {
        "batch_id": batch_id, "mode": "sequential", "requested": len(documents),
        "successful": successful, "failed": len(documents) - successful,
        "seconds": round(perf_counter() - total_start, 2), "browser_used": False,
        "results": ordered, "combined_pdf": str(combined) if combined else None,
        "error": failure or None, "events": events,
    }
    (directory / "resultado.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({key: report[key] for key in (
        "successful", "failed", "seconds", "combined_pdf"
    )}, ensure_ascii=True), flush=True)
    print("Relatorio: " + str(directory / "resultado.json"), flush=True)
    return 0 if successful == len(documents) and not failure else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ctes", nargs="+", help="Ex.: 2-10-10402 1-10-23167 11-10-397")
    group.add_argument("--file", type=Path, help="Lista UTF-8, um CT-e por linha.")
    args = parser.parse_args()
    try:
        raw = args.file.read_text(encoding="utf-8-sig") if args.file else "\n".join(args.ctes)
        documents = parse_documents(raw)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    return asyncio.run(run_batch(documents))


if __name__ == "__main__":
    raise SystemExit(main())
