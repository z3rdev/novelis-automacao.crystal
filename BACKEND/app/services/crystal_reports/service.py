import json
import os
import re
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from typing import Any
from uuid import uuid4

from app.automation.cancellable_process import run_process
from app.config.legacy_config import LegacyConfig
from app.config.settings import Settings
from app.services.crystal_reports.code128 import create_code128_bitmap, validate_code128
from app.services.crystal_reports.connection import database_configured, report_database
from app.services.crystal_reports.models import DacteRequest
from app.services.crystal_reports.qr_code import (
    create_qr_bitmap,
    load_qr_reference,
    validate_independent_qr,
)
from app.services.crystal_reports.validation import read_pdf_symbols


class CrystalReportError(RuntimeError):
    def __init__(self, message: str, status_code: int = 503) -> None:
        super().__init__(message)
        self.status_code = status_code


class CrystalReportService:
    def __init__(self, settings: Settings, config: LegacyConfig) -> None:
        self.settings = settings
        self.config = config
        self._lock = Lock()

    @property
    def report_path(self) -> Path:
        configured = self.config.get("CRYSTAL_DACTE_RPT_PATH")
        if configured:
            return Path(configured).expanduser().resolve()
        return self.settings.backend_root.parent / "assets" / "reports" / "dacte.rpt"

    def inspect(self) -> dict[str, Any]:
        result = self._execute({"action": "inspect"})
        references = []
        for report in [result["report"], *result["subreports"]]:
            for formula in report["formulas"]:
                text = "\n".join(
                    line
                    for line in formula["text"].splitlines()
                    if not line.lstrip().startswith("'")
                )
                functions = sorted(set(re.findall(r"\b((?:BCS|rod)\w*)\s*\(", text)))
                if functions:
                    references.append(
                        {
                            "report": report["name"],
                            "formula": formula["name"],
                            "functions": functions,
                        }
                    )
        result["external_function_references"] = references
        return result

    def export(self, document: DacteRequest) -> Path:
        pdf_engine = self.config.get("CRYSTAL_PDF_ENGINE", "windows").lower()
        if pdf_engine not in {"windows", "native"}:
            raise CrystalReportError("CRYSTAL_PDF_ENGINE precisa ser windows ou native.", 422)
        qr_provider = self.config.get("CRYSTAL_QR_PROVIDER", "python").lower()
        if qr_provider not in {"python", "report"}:
            raise CrystalReportError("CRYSTAL_QR_PROVIDER precisa ser python ou report.", 422)
        code128_provider = self.config.get("CRYSTAL_CODE128_PROVIDER", qr_provider).lower()
        if code128_provider not in {"python", "report"}:
            raise CrystalReportError("CRYSTAL_CODE128_PROVIDER precisa ser python ou report.", 422)
        try:
            db = report_database(self.config)
        except ValueError as exc:
            raise CrystalReportError(str(exc), 422) from exc
        if not database_configured(db):
            raise CrystalReportError("Configure CRYSTAL_DB_* ou CONSULTA_DB_* no backend.", 422)
        output_dir = self.settings.storage_dir / "reports" / "dacte"
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = (
            f"dacte-{document.filial}-{document.serie}-{document.documento}-{uuid4().hex}.pdf"
        )
        output = output_dir / filename
        try:
            with TemporaryDirectory(prefix="qr-", dir=output_dir) as temporary:
                payload = {
                    "action": "export",
                    "document": document.model_dump(),
                    "output_path": str(output.resolve()),
                    "database": db,
                    "pdf_engine": pdf_engine,
                    "qr_provider": qr_provider,
                    "code128_provider": code128_provider,
                }
                if qr_provider == "python" or code128_provider == "python":
                    reference = load_qr_reference(db, document)
                if qr_provider == "python":
                    image_path = Path(temporary) / "qr.bmp"
                    create_qr_bitmap(reference, image_path)
                    payload["qr_image_path"] = str(image_path.resolve())
                if code128_provider == "python":
                    barcode_path = Path(temporary) / "code128.bmp"
                    create_code128_bitmap(reference.access_key, barcode_path)
                    payload["code128_image_path"] = str(barcode_path.resolve())
                self._execute(payload)
            if not output.is_file() or output.stat().st_size < 5:
                raise CrystalReportError("Crystal Reports nao produziu um PDF.", 502)
            with output.open("rb") as stream:
                if stream.read(5) != b"%PDF-":
                    raise CrystalReportError(
                        "Crystal Reports retornou um arquivo que nao e PDF.", 502
                    )
            if qr_provider == "python":
                validate_independent_qr(output, reference)
            elif code128_provider == "python":
                symbols, _ = read_pdf_symbols(output)
                validate_code128(symbols, reference.access_key)
            return output
        except (ValueError, ImportError) as exc:
            output.unlink(missing_ok=True)
            raise CrystalReportError("Validacao DACTE: " + str(exc), 422) from None
        except Exception:
            output.unlink(missing_ok=True)
            raise

    def _execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        if os.name != "nt":
            raise CrystalReportError("A exportacao RPT exige Windows e Crystal Reports XI 32 bits.")
        if payload.get("action") != "environment" and (
            not self.report_path.is_file() or self.report_path.suffix.lower() != ".rpt"
        ):
            raise CrystalReportError(
                "Relatorio nao encontrado. Configure CRYSTAL_DACTE_RPT_PATH.", 422
            )
        windows = Path(os.environ.get("SystemRoot", r"C:\Windows"))
        powershell = windows / "SysWOW64" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        if not powershell.is_file():
            raise CrystalReportError("Windows PowerShell 32 bits nao encontrado.")
        qr_provider = self.config.get("CRYSTAL_QR_PROVIDER", "python").lower()
        request = {
            "qr_provider": qr_provider,
            "code128_provider": self.config.get("CRYSTAL_CODE128_PROVIDER", qr_provider).lower(),
            **payload,
            "report_path": str(self.report_path),
            "prog_id": self.config.get("CRYSTAL_REPORTS_PROGID", ""),
        }
        if not self._lock.acquire(blocking=False):
            raise CrystalReportError(
                "Crystal Reports esta ocupado. Tente novamente em instantes.", 409
            )
        try:
            try:
                result = run_process(
                    [
                        str(powershell),
                        "-NoProfile",
                        "-NonInteractive",
                        "-STA",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        str(Path(__file__).with_name("worker.ps1")),
                    ],
                    input=json.dumps(request, ensure_ascii=True),
                    text=True,
                    encoding="utf-8",
                    capture_output=True,
                    check=False,
                    timeout=max(
                        10, min(self.config.int("CRYSTAL_EXPORT_TIMEOUT_SECONDS", 120), 600)
                    ),
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except subprocess.TimeoutExpired as exc:
                progress = exc.stderr or b""
                if isinstance(progress, bytes):
                    progress = progress.decode("utf-8", errors="replace")
                stages = [
                    line.removeprefix("CRYSTAL_STAGE=")
                    for line in progress.splitlines()
                    if line.startswith("CRYSTAL_STAGE=")
                ]
                stage = stages[-1] if stages else "inicializacao"
                raise CrystalReportError(
                    f"Tempo limite excedido no Crystal Reports ({stage}).", 504
                ) from None
            except OSError:
                raise CrystalReportError(
                    "Nao foi possivel iniciar o Crystal Reports local."
                ) from None
            try:
                lines = result.stdout.splitlines()
                framed = [
                    line[len("CRYSTAL_RESULT=") :]
                    for line in lines
                    if line.startswith("CRYSTAL_RESULT=")
                ]
                response = json.loads(
                    framed[-1] if framed else result.stdout.strip().lstrip("\ufeff")
                )
            except (json.JSONDecodeError, TypeError):
                raise CrystalReportError(
                    "O processo Crystal Reports encerrou sem uma resposta valida.", 502
                ) from None
            if result.returncode or not response.get("ok"):
                message = str(response.get("error") or "Falha no Crystal Reports.")
                password = str(payload.get("database", {}).get("password") or "")
                if password:
                    message = message.replace(password, "<redacted>")
                stage = str(response.get("stage") or "engine")
                if "u2lcom" in message.lower() or "ufl" in message.lower():
                    raise CrystalReportError(
                        "O RPT depende de funcoes UFL ausentes no Crystal local. "
                        "Instale os componentes adicionais usados pelo relatorio; "
                        "consulte /api/reports/dacte/inspect. Detalhe: " + message,
                        503,
                    )
                raise CrystalReportError(f"Crystal Reports ({stage}): {message}", 502)
            return response
        finally:
            self._lock.release()
