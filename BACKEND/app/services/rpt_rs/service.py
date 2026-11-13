"""Generate local experimental PDFs and retain renderer fidelity diagnostics."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from app.services.crystal_reports.code128 import create_code128_bitmap
from app.services.crystal_reports.connection import database_configured, report_database
from app.services.crystal_reports.qr_code import (
    create_qr_bitmap,
    load_qr_reference,
    validate_independent_qr,
)
from app.services.rpt_rs.client import RptWorker
from app.services.rpt_rs.model import prepare_model
from app.services.rpt_rs.sql_server import fetch_datasets


class RptRsService:
    def __init__(self, settings, config):
        self.settings, self.config = settings, config
        self.root = settings.backend_root.parent
        configured = config.get("RPT_RS_WORKER_PATH")
        executable = Path(configured) if configured else self.root / "rpt-worker/target/debug/novelis-rpt-worker.exe"
        self.worker = RptWorker(executable)
        configured_report = config.get("CRYSTAL_DACTE_RPT_PATH")
        self.report_path = Path(configured_report) if configured_report else self.root / "assets/reports/dacte.rpt"

    def inspect(self):
        return self.worker.call("inspect", report_path=str(self.report_path))

    def export_candidate(self, document) -> Path:
        database = report_database(self.config)
        if not database_configured(database):
            raise ValueError("Configure o acesso SQL do DACTE.")
        directory = self.settings.storage_dir / "reports/rpt-rs"
        directory.mkdir(parents=True, exist_ok=True)
        output = directory / f"candidate-{document.filial}-{document.serie}-{document.documento}-{uuid4().hex}.pdf"
        reference = load_qr_reference(database, document)
        report_hash = hashlib.sha256(self.report_path.read_bytes()).hexdigest()
        original = self.inspect()
        with TemporaryDirectory(prefix="symbols-", dir=directory) as temporary:
            qr, barcode = Path(temporary) / "qr.bmp", Path(temporary) / "code128.bmp"
            create_qr_bitmap(reference, qr)
            create_code128_bitmap(reference.access_key, barcode)
            model, adaptation = prepare_model(original["model"], qr.read_bytes(), barcode.read_bytes())
        plan = self.worker.call("plan", model=model)
        datasets, sql_evidence = fetch_datasets(plan["scopes"], database, document)
        result = self.worker.call("render", model=model, datasets=datasets, output_path=str(output),
            parameters={"P_CODFIL": document.filial, "P_SERCON": document.serie,
                        "P_CODCON_INI": document.documento, "P_CODCON_FIN": document.documento})
        evidence = {"engine": "rpt-rs", "document": document.model_dump(), "revision": result["revision"],
            "adaptation": adaptation, "datasets": sql_evidence, "render": result,
            "rpt_sha256": report_hash,
            "rpt_unchanged": hashlib.sha256(self.report_path.read_bytes()).hexdigest() == report_hash,
            "database_access_credentials_recorded": False, "production_ready": False}
        try:
            validate_independent_qr(output, reference)
            evidence["symbols_match_database"] = True
        except ValueError as error:
            evidence.update(symbols_match_database=False, symbol_error=str(error))
        output.with_suffix(".json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return output
