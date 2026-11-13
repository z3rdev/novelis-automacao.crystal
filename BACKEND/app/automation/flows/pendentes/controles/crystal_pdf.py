import os
import shutil
from pathlib import Path
from uuid import uuid4

from app.automation.cancellation import run_blocking
from app.automation.flows.flow_events import emit_step, emit_warn
from app.services.crystal_reports.models import DacteRequest
from app.services.crystal_reports.service import CrystalReportError, CrystalReportService
from app.services.crystal_reports.validation import read_pdf_symbols
from app.services.cte_pdf_files import find_pdf_evidence, pdf_target


class CrystalPdfRunner:
    def __init__(self, settings, legacy_config, emit):
        self.settings = settings
        self.emit = emit
        self.legacy_config = legacy_config
        self.service = None

    async def run(self, browser, pdf_config, plan, request, run_id, config):
        items = [item for item in plan["checked"] if item["cte"] in plan["faltandoPdf"]]
        if not items:
            await emit_step(self.emit, run_id, "crystal_pdf.skip",
                            f"{len(plan['checked'])} PDF(s) ja disponiveis na pasta de rede; nenhum PDF gerado novamente.",
                            {"available": len(plan["checked"]), "total": 0})
            return
        if request.dry_run:
            await emit_step(self.emit, run_id, "crystal_pdf.dry_run", "Simulacao: nenhum PDF foi gerado.")
            return
        failures = []
        for index, item in enumerate(items):
            cte = item["cte"]
            row = item["row"]
            await emit_step(
                self.emit, run_id, "crystal_pdf.progress",
                f"Crystal PDF {index + 1}/{len(items)}: {cte}, diretamente pelo banco.",
                {"current": index + 1, "total": len(items), "cte": cte, "source": "crystal"},
            )
            try:
                document = DacteRequest(
                    filial=int(row["filial"]), serie=str(row["serie"]), documento=int(row["documento"])
                )
                target = self._target(pdf_config, document)
                existing = await run_blocking(find_pdf_evidence, target.parent.parent, row)
                if existing:
                    await emit_step(self.emit, run_id, "crystal_pdf.reused", f"PDF ja disponivel para {cte}; geracao dispensada.",
                                    {"cte": cte, "pdfFile": str(existing), "source": "existing"})
                    continue
                if self.service is None:
                    self.service = CrystalReportService(self.settings, self.legacy_config)
                output = await run_blocking(self.service.export, document)
                await emit_step(
                    self.emit, run_id, "crystal_pdf.generated", f"PDF gerado pelo Crystal para {cte}.",
                    {"cte": cte, "pdfFile": str(output), "source": "crystal"},
                )
                await run_blocking(check_automation_pdf, output, document)
                await run_blocking(publish_pdf, output, target)
                await emit_step(
                    self.emit, run_id, "crystal_pdf.saved", f"PDF Crystal salvo para {cte}.",
                    {"cte": cte, "pdfFile": str(target), "source": "crystal"},
                )
            except (CrystalReportError, ValueError, OSError, ImportError) as exc:
                failures.append({"cte": cte, "message": str(exc)})
                await emit_warn(
                    self.emit, run_id, "crystal_pdf.error",
                    f"Crystal PDF falhou para {cte}: {exc}. Rodopar permanece desabilitado.",
                    {"cte": cte, "source": "crystal", "error": str(exc)},
                )
                if config.get("stopOnError"):
                    raise
        if failures:
            detail = "; ".join(f"{item['cte']}: {item['message']}" for item in failures)
            raise RuntimeError(f"PDF Crystal com pendencias: {detail}")

    def _target(self, config, document):
        base = Path(config.get("downloadTargetDir") or "captures/rodopar-pdfs-downloads")
        if not base.is_absolute():
            base = self.settings.backend_root.parent / base
        return pdf_target(base, document.model_dump())


def check_automation_pdf(path: Path, document: DacteRequest) -> None:
    symbols, _ = read_pdf_symbols(path)
    qrs = [symbol["value"] for symbol in symbols if symbol["format"] == "QR Code"]
    if any(value.endswith(" Demo") for value in qrs):
        raise ValueError(f"QR Code alterado pelo componente DEMO. PDF de teste preservado em {path}; nao liberado como anexo")
    keys = [symbol["value"] for symbol in symbols if symbol["format"] == "Code 128"]
    matching = [
        key for key in keys if len(key) == 44 and key.isdecimal()
        and int(key[25:34]) == document.documento
        and document.serie.isdecimal() and int(key[22:25]) == int(document.serie)
    ]
    if not matching or not any(key in qr for key in matching for qr in qrs):
        raise ValueError(f"Chave/QR Code do PDF nao conferem com o CTe solicitado. Teste preservado em {path}")


def publish_pdf(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix("." + uuid4().hex + ".part")
    try:
        shutil.copy2(source, temporary)
        # Keep any evidence already present rather than replacing it on a race.
        if not target.exists():
            os.rename(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
