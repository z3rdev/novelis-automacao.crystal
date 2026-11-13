"""Bind an integrated installer to its actual public and proprietary build inputs."""
import argparse
import datetime
import hashlib
import json
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def inventory(folder):
    return {path.relative_to(folder).as_posix(): digest(path)
            for path in sorted(folder.rglob("*")) if path.is_file()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--setup", type=Path, required=True)
    parser.add_argument("--mode", choices=["development", "distribution"], required=True)
    args = parser.parse_args()
    inputs = ROOT / "runtime/installer-inputs"
    crystal = json.loads((inputs / "crystal/crystal-runtime.manifest.json").read_text())
    if digest(inputs / "crystal" / crystal["filename"]) != crystal["sha256"]:
        raise RuntimeError("Staged Crystal MSI differs from its manifest")
    version = json.loads((ROOT / "runtime/hub-build-config.json").read_text(encoding="utf-8-sig"))["version"]
    version_source = (ROOT / "DESKTOP/automacao_novelis_desktop/config.py").read_text(encoding="utf-8")
    if re.search(r'APP_VERSION\s*=\s*"([^"]+)"', version_source).group(1) != version:
        raise RuntimeError("Application version changed during build; rebuild before delivery")
    tauri_exe = ROOT / "FRONTEND-HUB/src-tauri/target/release/novelis-cargo-hub.exe"
    raw = tauri_exe.read_bytes()
    pe_offset = struct.unpack_from("<I", raw, 0x3c)[0]
    if raw[pe_offset:pe_offset + 4] != b"PE\0\0" or struct.unpack_from("<H", raw, pe_offset + 4)[0] != 0x8664:
        raise RuntimeError("Tauri executable is not AMD64 PE")
    result = {"filename": args.setup.name, "sha256": digest(args.setup),
        "bytes": args.setup.stat().st_size, "build_mode": args.mode,
        "built_at": datetime.datetime.now(datetime.UTC).isoformat(), "app_version": version,
        "frontend": "FRONTEND-HUB / Tauri", "tauri_exe_sha256": digest(tauri_exe), "tauri_architecture": "x64",
        "frontend_files": inventory(ROOT / "FRONTEND-HUB/dist-desktop"),
        "python_runtime": json.loads((ROOT / "installer/backend/python-runtime.lock.json").read_text()),
        "webview2": json.loads((inputs / "webview2/webview2.manifest.json").read_text()),
        "crystal": {key: crystal[key] for key in ["filename", "sha256", "runtime_version", "architecture"]},
        "wheels": inventory(inputs / "wheels"),
        "clean_machine_homologation": "pending", "production_ready": False,
        "published": False, "licensing_status": "see_crystal_approval_and_homologation"}
    revision = re.search(r"-(r[1-9][0-9]*)-", args.setup.name)
    result["installer_revision"] = revision.group(1) if revision else None
    result["configuration_timing"] = "before_bootstrap_run"
    result["configuration_sources"] = {name: digest(ROOT / name) for name in [
        "installer/AutomacaoNovelis.iss", "installer/backend/Configuration.iss",
        "installer/backend/Hub.iss", "installer/backend/OperationalConfiguration.iss",
        "installer/backend/Preparation.iss", "scripts/bootstrap.ps1", "scripts/build-installer.ps1",
        "scripts/setup/environment_payload.py", "scripts/setup/protect-operational-env.ps1",
        "scripts/setup/verify_backend.py",
        "scripts/setup/launch_backend.py",
        "scripts/setup/network_access.py", "scripts/setup/windows_network.py",
        "FRONTEND-HUB/src-tauri/src/backend.rs",
    ]}
    result["backend_query_sources"] = {name: digest(ROOT / name) for name in [
        "BACKEND/app/data/consulta_db.py",
        "BACKEND/app/automation/flows/pendentes/controles/plan.py",
        "BACKEND/app/automation/flows/pendentes/steps/pendentes.py",
        "scripts/diagnose-consulta-sql.py",
        "BACKEND/app/automation/flows/pendentes/controles/execution_scope.py",
    ]}
    result["dacte_sources"] = {name: digest(ROOT / name) for name in [
        "BACKEND/app/services/crystal_reports/code128.py",
        "BACKEND/app/services/crystal_reports/code128-picture.ps1",
        "BACKEND/app/services/crystal_reports/worker.ps1",
        "BACKEND/app/services/crystal_reports/service.py",
        "BACKEND/app/services/crystal_reports/qr_code.py",
        "BACKEND/app/services/crystal_reports/diagnostics.py",
        "BACKEND/app/services/cte_pdf_files.py",
        "BACKEND/app/automation/flows/pendentes/controles/crystal_pdf.py",
        "BACKEND/app/tools/dacte_components.py",
        "BACKEND/app/tools/dacte_setup.py",
        "BACKEND/pyproject.toml",
    ]}
    result["operator_and_live_files_sources"] = {name: digest(ROOT / name) for name in [
        "BACKEND/app/api/routers/sessions.py",
        "BACKEND/app/services/device_identity.py",
        "BACKEND/app/services/session_audit.py",
        "BACKEND/app/infrastructure/session_audit_db.py",
        "BACKEND/app/services/pending_documents.py",
        "BACKEND/app/services/hub_service.py",
        "BACKEND/app/domain/run_state.py",
        "BACKEND/app/main.py",
        "FRONTEND-HUB/src/components/app/session-gate.tsx",
        "FRONTEND-HUB/src/components/app/period-select.tsx",
        "FRONTEND-HUB/src/routes/pendentes.tsx",
        "FRONTEND-HUB/src/services/http.ts",
    ]}
    private = "-PRIVADO" in args.setup.name
    result["operational_configuration"] = {"included": private,
        "contains_operational_credentials": private, "values_recorded_in_manifest": False,
        "license_keys_in_profile": False}
    args.setup.with_suffix(".manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"filename": result["filename"], "sha256": result["sha256"],
                      "bytes": result["bytes"], "production_ready": False}))


if __name__ == "__main__":
    main()
