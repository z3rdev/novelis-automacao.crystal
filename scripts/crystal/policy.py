"""Fail-closed controls shared by the MSI build and application packaging."""
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

VERSION = "11.5.0.313"
PROGID = "CrystalDesignRunTime.Application.11"


def redact(text: str, key: str) -> str:
    for value in (key, key.replace("-", "")):
        text = re.sub(re.escape(value), "<redacted>", text, flags=re.I)
    return text


def restrict_directory(directory: Path) -> None:
    """Restrict license-bearing local artifacts without revoking leaf file access."""
    if os.name != "nt":
        return
    sid = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                          "[Security.Principal.WindowsIdentity]::GetCurrent().User.Value"],
                         capture_output=True, text=True, check=True).stdout.strip()
    for node in [directory, *directory.rglob("*")]:
        rights = "(OI)(CI)F" if node.is_dir() else "F"
        subprocess.run(["icacls", str(node), "/inheritance:r", "/grant:r", f"*{sid}:{rights}",
                        f"*S-1-5-18:{rights}", f"*S-1-5-32-544:{rights}", "/Q"],
                       capture_output=True, check=True)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_key(path: Path, field: str = "KEY") -> str:
    # Never include file contents, key, or a fingerprint of the key in errors.
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
    if field:
        pattern = r"[ \t]*" + re.escape(field) + r"(?:[ \t]*[:=\-][ \t]*|[ \t]+)(.+?)[ \t]*"
        matches = [match[1] for line in text.splitlines() if (match := re.fullmatch(pattern, line, re.I))]
        if len(matches) != 1:
            raise ValueError("Fonte de PIDKEY deve conter exatamente um campo autorizado.")
        text = matches[0]
    key = text.strip()
    if not re.fullmatch(r"[A-Za-z0-9]{5}-[A-Za-z0-9]{7}-[A-Za-z0-9]{7}-[A-Za-z0-9]{4}", key):
        raise ValueError("PIDKEY fora do formato XI R2 esperado; valor omitido.")
    return key


def verify_modules(directory: Path, lock: dict) -> list[dict]:
    result = []
    for module in lock["modules"]:
        path = directory / module["filename"]
        if not path.is_file() or sha256(path).lower() != module["sha256"].lower():
            raise ValueError("Merge module ausente ou diferente do inventario: " + module["filename"])
        result.append({"filename": path.name, "sha256": sha256(path), "bytes": path.stat().st_size})
    if len(result) != 4 or lock["runtime_version"] != VERSION:
        raise ValueError("Conjunto RDC 11.5 x86 incompleto.")
    return result


def distribution_approval(path: Path | None, package_hash: str | None = None) -> dict:
    if path is None or not path.is_file():
        raise ValueError("Distribuicao bloqueada: faltam aprovacoes de procedencia e licenca.")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if (data.get("schema_version") != 1 or data.get("runtime_version") != VERSION
            or not data.get("approved_by") or not data.get("approved_at")
            or data.get("deployment_scope") not in {"internal", "external", "oem"}):
        raise ValueError("Aprovacao de distribuicao incompleta.")
    for name in ("provenance", "license"):
        section = data.get(name, {})
        if section.get("approved") is not True or not section.get("evidence_file"):
            raise ValueError("Distribuicao bloqueada: aprovacao pendente de " + name)
        evidence = Path(section["evidence_file"])
        if not evidence.is_absolute():
            evidence = path.parent / evidence
        if not evidence.is_file() or sha256(evidence).lower() != str(section.get("sha256", "")).lower():
            raise ValueError("Evidencia ausente ou adulterada: " + name)
    if package_hash is not None and str(data.get("package_sha256", "")).lower() != package_hash.lower():
        raise ValueError("Aprovacao nao corresponde ao MSI selecionado.")
    return data


def verify_payload(manifest_path: Path, mode: str, approval_path: Path | None = None) -> tuple[dict, Path]:
    data = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    package = manifest_path.parent / data["filename"]
    if (Path(data["filename"]).name != data["filename"] or not package.is_file()
            or sha256(package) != data.get("sha256") or data.get("runtime_version") != VERSION
            or data.get("architecture") != "x86" or data.get("structure_verified") is not True
            or data.get("audit", {}).get("execute_sequence_verified") is not True
            or data.get("withdrawn") is True):
        raise ValueError("MSI Crystal sem integridade/estrutura comprovada.")
    if mode == "distribution":
        if data.get("build_mode") != "distribution":
            raise ValueError("MSI de desenvolvimento nao pode ser redistribuido.")
        distribution_approval(approval_path, data["sha256"])
    elif data.get("build_mode") != "development":
        raise ValueError("Build de teste exige pacote marcado development.")
    return data, package
