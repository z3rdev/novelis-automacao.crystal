"""Controlled, read-only SQL DACTE test; writes local PDF and non-license evidence."""
import argparse
import ctypes
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "BACKEND"))
from app.config.legacy_config import LegacyConfig
from app.config.settings import Settings
from app.services.crystal_reports.diagnostics import diagnose, write_diagnostic
from app.services.crystal_reports.models import DacteRequest
from app.services.crystal_reports.service import CrystalReportService
from crystal.policy import PROGID, verify_payload


class EvidenceService(CrystalReportService):
    def _execute(self, payload):
        if payload.get("action") == "export" and payload.get("pdf_engine") == "native":
            self.native_execution_attempted = True
        result = super()._execute(payload)
        if payload.get("action") == "export":
            self.execution = {name: result.get(name) for name in ("engine", "records", "execution_evidence")}
            if payload.get("pdf_engine") == "native":
                self.native_capture = self.settings.storage_dir / "native-before-validation.pdf"
                shutil.copyfile(payload["output_path"], self.native_capture)
        return result


def probe():
    executable = Path(os.environ["SystemRoot"]) / "SysWOW64/WindowsPowerShell/v1.0/powershell.exe"
    result = subprocess.run([str(executable), "-NoProfile", "-NonInteractive", "-STA", "-ExecutionPolicy",
                             "Bypass", "-File", str(ROOT / "installer/crystal/inspect-runtime.ps1")],
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
    lines = [line[len("CRYSTAL_PROBE="):] for line in result.stdout.splitlines() if line.startswith("CRYSTAL_PROBE=")]
    if not lines:
        raise ValueError("Diagnostico x86 sem resposta; detalhes nativos omitidos.")
    return json.loads(lines[-1])


def clean_baseline_matches(baseline, current, installation, manifest):
    """Evidence consistency is required, but never substitutes for human VM approval."""
    return bool(
        baseline.get("machine_uuid") and baseline["machine_uuid"] == current.get("machine_uuid")
        and baseline.get("schema_version") == 1 and baseline.get("process_bits") == 32
        and baseline.get("any_crystal_registered") is False and baseline.get("full_editor_installed") is False
        and baseline.get("installed_crystal_products") == []
        and len(baseline.get("dlls", [])) == 5
        and all(dll.get("exists") is False for dll in baseline["dlls"])
        and installation.get("status") in {"installed_verified", "restart_required"}
        and installation.get("package_sha256") == manifest.get("sha256")
        and baseline.get("checked_at", "z") < installation.get("checked_at", "")
        and not current.get("full_editor_installed")
    )


def run(args):
    if not args.authorized_test:
        raise ValueError("Informe --authorized-test somente no ambiente de teste autorizado.")
    current = probe()
    directory = args.output
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "runtime-state.json").write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    if args.baseline_only:
        return {"status": "baseline_captured", "baseline": str(directory / "runtime-state.json"),
                "production_ready": False}, 0
    if not args.expected_account or current.get("identity", "").casefold() != args.expected_account.casefold():
        raise ValueError("Execute o teste sob a conta real do backend informada em --expected-account.")
    if not all((args.xml_reference, args.filial is not None, args.serie, args.documento is not None)):
        raise ValueError("Informe XML, filial, serie e documento do CT-e autorizado para teste.")
    clean_evidence = False
    if args.environment == "clean-vm":
        if not all((args.baseline, args.install_result, args.manifest)):
            raise ValueError("VM limpa exige baseline anterior, resultado de instalacao e manifesto MSI.")
        manifest, _ = verify_payload(args.manifest, "development")
        baseline = json.loads(args.baseline.read_text(encoding="utf-8-sig"))
        installation = json.loads(args.install_result.read_text(encoding="utf-8-sig"))
        clean_evidence = clean_baseline_matches(baseline, current, installation, manifest)
        api = ctypes.WinDLL("msi")
        api.MsiQueryProductStateW.argtypes = [ctypes.c_wchar_p]
        if not clean_evidence or api.MsiQueryProductStateW(manifest["audit"]["product_code"]) != 5:
            raise ValueError("Evidencias nao comprovam instalacao deste MSI sobre baseline sem Crystal.")
        if args.require_reboot and installation["before"]["last_boot_utc"] == current["last_boot_utc"]:
            raise ValueError("Reinicializacao posterior a instalacao ainda nao comprovada.")
    settings = Settings(storage_dir=directory)
    config = LegacyConfig(settings)
    config.values = {**config.values, "CRYSTAL_REPORTS_PROGID": PROGID,
                     "CRYSTAL_QR_PROVIDER": "python", "CRYSTAL_PDF_ENGINE": "windows"}
    service = EvidenceService(settings, config)
    document = DacteRequest(filial=args.filial, serie=args.serie, documento=args.documento)
    report = diagnose(service, connect=True, document=document, xml_reference=args.xml_reference)
    report.update(environment=args.environment, runtime_probe=current,
                  clean_vm_evidence_consistent=clean_evidence,
                  execution=getattr(service, "execution", {}),
                  licensing_approved=False, homologation_approval="pending", production_ready=False)
    execution = report["execution"]
    details = execution.get("execution_evidence") or {}
    required = {"OpenReport", "ReadRecords", "AddPictureObject", "PrintOutEx"}
    pipeline_ok = (required.issubset(details.get("operations", [])) and details.get("pictures_added", 0) > 0
                   and details.get("process_bits") == 32 and execution.get("engine") == PROGID
                   and details.get("identity", "").casefold() == args.expected_account.casefold()
                   and execution.get("records", 0) > 0)
    report["pipeline_verified"] = pipeline_ok
    if args.native_pdf:
        from app.services.crystal_reports.validation import validate_pdf_codes
        config.values["CRYSTAL_PDF_ENGINE"] = "native"
        try:
            pdf = service.export(document)
            report["native_pdf"] = {"pdf": str(pdf), "execution": service.execution,
                                    **validate_pdf_codes(pdf, args.xml_reference, directory / "native-pdf-pages")}
        except Exception as error:
            report["native_pdf"] = {"status": "failed", "error": "Exportador nativo falhou; detalhes omitidos.",
                                    "http_status": getattr(error, "status_code", None),
                                    "failure_type": type(error).__name__,
                                    "execution_attempted": getattr(service, "native_execution_attempted", False)}
            if not report["native_pdf"]["execution_attempted"]:
                report["native_pdf"].update(status="prerequisite_failed",
                                           error="Pre-requisito de dados/QR falhou antes da chamada ao exportador.")
            captured = getattr(service, "native_capture", None)
            if captured and captured.is_file():
                report["native_pdf"].update(status="output_validation_failed",
                                           error="O exportador gerou PDF, mas a validacao dos simbolos falhou.")
                report["native_pdf"]["captured_pdf"] = str(captured)
                report["native_pdf"]["symbols"] = validate_pdf_codes(
                    captured, args.xml_reference, directory / "native-pdf-pages")
                report["native_pdf"]["execution"] = service.execution
    report["windows_pdf_test_passed"] = bool(current.get("functional") and pipeline_ok
                                             and report["status"] == "technical_ready"
                                             and report["checks"]["symbols"]["status"] == "ok")
    passed = (current.get("functional") and pipeline_ok and report["status"] == "technical_ready"
              and report["checks"]["symbols"]["status"] == "ok"
              and (not args.native_pdf or report["native_pdf"]["status"] == "ok"))
    report["test_passed"] = bool(passed)
    write_diagnostic(report, directory)
    return {"status": "passed" if passed else "pending", "environment": args.environment,
            "report": str(directory / "dacte-diagnostic.json"), "production_ready": False}, 0 if passed else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorized-test", action="store_true")
    parser.add_argument("--baseline-only", action="store_true")
    parser.add_argument("--environment", choices=["development", "clean-vm"], default="development")
    parser.add_argument("--expected-account")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--install-result", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--require-reboot", action="store_true")
    parser.add_argument("--native-pdf", action="store_true")
    parser.add_argument("--xml-reference", type=Path)
    parser.add_argument("--filial", type=int)
    parser.add_argument("--serie")
    parser.add_argument("--documento", type=int)
    parser.add_argument("--output", type=Path, default=ROOT / "runtime/crystal-homologation" /
                        datetime.now(UTC).strftime("%Y%m%d-%H%M%SZ"))
    args = parser.parse_args()
    try:
        result, code = run(args)
    except Exception:
        result, code = {"status": "blocked", "production_ready": False,
                        "message": "Pre-condicao ou teste falhou; verifique conta, baseline, integridade e parametros."}, 2
    print(json.dumps(result))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
