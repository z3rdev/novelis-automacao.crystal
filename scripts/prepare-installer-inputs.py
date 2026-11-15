"""Stage sanitized defaults and only explicitly licensed vendor packages."""
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "setup"))
from crystal.policy import restrict_directory, verify_payload
from environment_payload import assignments
from environment_payload import stage as stage_environment

ROOT = Path(__file__).resolve().parents[1]
SECRET = re.compile(r"(?:^|_)(?:PASS|PASSWORD|PASSWD|PWD|SECRET|TOKEN|COOKIE|CREDENTIALS?|API_KEY|PRIVATE_KEY)(?:$|_VALUE$)|(?:^|_)USER(?:NAME)?$", re.I)
FACTORY_PATHS = {"STORAGE_DIR": "../runtime", "LEGACY_PROJECT_DIR": "",
                 "XML_SEFAZ_DOWNLOAD_DIR": r"\\192.168.254.250\rede\Publico\AUTOMAÇÃO-CTE\XML-SEFAZ",
                 "RODOPAR_PDF_DOWNLOAD_TARGET_DIR": r"\\192.168.254.250\rede\Publico\AUTOMAÇÃO-CTE\PDFS-RODOPAR",
                 "CRYSTAL_DACTE_RPT_PATH": "",
                 "CRYSTAL_REPORTS_PROGID": "CrystalDesignRunTime.Application.11"}


def private_input(directory: Path, filename: str) -> Path:
    path = (directory / filename).resolve()
    if not path.is_relative_to(directory.resolve()):
        raise RuntimeError("Componente fora do diretorio privado de distribuicao.")
    return path


def factory_environment(raw: str) -> str:
    lines = []
    for line in raw.lstrip("\ufeff").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            lines.append(line.rstrip())
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        unquoted = value.strip().strip("\"'")
        if key in FACTORY_PATHS:
            value = FACTORY_PATHS[key]
        elif key == "RODOPAR_BROWSER_ENABLED":
            value = "false"
        elif key == "PENDENTES_PDF_SOURCE":
            value = "crystal"
        elif SECRET.search(key) or re.match(r"^(?:CONSULTA|CRYSTAL)_DB_(?:SERVER|HOST|PORT|INSTANCE|DATABASE)$|^CHAMADOS_PG_(?:HOST|DATABASE|SSLROOTCERT)$", key):
            value = ""
        elif re.match(r"^[A-Za-z]:[\\/]", unquoted) or unquoted.startswith("\\\\"):
            value = ""
        elif key in {"AUTO_START_WITH_SERVICE", "AUTO_RUN_ENABLED", "AUTO_CONSULT_ENABLED"}:
            value = "false"
        lines.append(key + "=" + value)
    return "\n".join(lines) + "\n"


def prepare(root: Path = ROOT, mode: str = "distribution", crystal_manifest: Path | None = None,
            approval: Path | None = None, operational_env: Path | None = None) -> dict:
    target = root / "runtime" / "installer-inputs"
    target.mkdir(parents=True, exist_ok=True)
    # A rejected build must not leave an earlier staged Crystal package usable by ISCC.
    crystal_dir = target / "crystal"
    if crystal_dir.is_dir():
        for old in crystal_dir.iterdir():
            if old.is_file():
                old.unlink()
    source = root / "BACKEND" / ".env.example"
    defaults = factory_environment(source.read_text(encoding="utf-8-sig"))
    (target / "BACKEND.env.example").write_text(defaults, encoding="utf-8")
    report_dir = root / "assets" / "reports"
    manifest = json.loads((report_dir / "dacte.manifest.json").read_text(encoding="utf-8"))
    if hashlib.sha256((report_dir / "dacte.rpt").read_bytes()).hexdigest() != manifest["sha256"]:
        raise RuntimeError("RPT difere do manifesto. Repita package-dacte-report.py.")
    if manifest["stored_credentials"] or manifest["has_saved_data"]:
        raise RuntimeError("O RPT nao passou pela sanitizacao para distribuicao.")
    catalog = json.loads((root / "installer" / "dacte" / "dependencies.json").read_text(encoding="utf-8"))
    payload = target / "dacte-vendor"
    payload.mkdir(exist_ok=True)
    for old in payload.iterdir():
        if old.is_file():
            old.unlink()
    included, assisted = [], []
    for component in catalog["components"]:
        if component["id"] == "crystal":
            if crystal_manifest is None:
                raise RuntimeError("Build bloqueado: forneca o manifesto do pre-requisito Crystal.")
            data, package = verify_payload(crystal_manifest, mode, approval)
            crystal_dir = target / "crystal"
            crystal_dir.mkdir(exist_ok=True)
            restrict_directory(crystal_dir)
            shutil.copyfile(package, crystal_dir / package.name)
            (crystal_dir / "crystal-runtime.manifest.json").write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8")
            included.append("crystal")
            continue
        if not component["redistribution_approved"]:
            assisted.append(component["id"])
            continue
        private = root / "installer" / "private-dacte"
        evidence = private_input(private, str(component.get("license_evidence") or "missing"))
        package = private_input(private, str(component.get("filename") or "missing"))
        if not evidence.is_file() or not package.is_file() or not component.get("sha256"):
            raise RuntimeError("Aprovacao incompleta do componente: " + component["id"])
        if hashlib.sha256(package.read_bytes()).hexdigest() != component["sha256"]:
            raise RuntimeError("Hash incorreto do componente: " + component["id"])
        shutil.copyfile(package, payload / package.name)
        included.append(component["id"])
    result = {"included_vendor_components": included, "assisted_components": assisted,
              "report_sha256": manifest["sha256"], "fiscal_validation": manifest["fiscal_validation"]}
    result["operational_configuration"] = stage_environment(root, defaults, operational_env, restrict_directory)
    active = (target / "private-configuration/BACKEND.env").read_text(encoding="utf-8") if operational_env else defaults
    values = assignments(active)
    qr_provider = values.get("CRYSTAL_QR_PROVIDER", "python").strip().strip('"').strip("'").lower()
    code128_provider = values.get("CRYSTAL_CODE128_PROVIDER", qr_provider).strip().strip('"').strip("'").lower()
    independent = {"barcodesoft": qr_provider == "python", "code128": code128_provider == "python"}
    result["independent_renderers"] = independent
    result["not_required_vendor_components"] = [name for name in assisted if independent.get(name)]
    result["assisted_components"] = [name for name in assisted if not independent.get(name)]
    (target / "dacte-build-report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["development", "distribution"], default="distribution")
    parser.add_argument("--crystal-manifest", type=Path)
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--operational-env", type=Path)
    args = parser.parse_args()
    try:
        result = prepare(mode=args.mode, crystal_manifest=args.crystal_manifest, approval=args.approval,
                         operational_env=args.operational_env)
    except Exception:
        raise SystemExit("Preparacao recusada. Verifique integridade, aprovacao e formato dos arquivos de entrada.") from None
    print(json.dumps(result, ensure_ascii=True))
