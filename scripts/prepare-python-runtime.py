"""Stage the complete official CPython NuGet tools directory for application-local use."""
import base64
import hashlib
import json
import os
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def extract_tools(package: Path, target: Path) -> None:
    with zipfile.ZipFile(package) as archive:
        for member in archive.infolist():
            name = member.filename.replace("\\", "/")
            if not name.startswith("tools/") or member.is_dir():
                continue
            output = (target / name.removeprefix("tools/")).resolve()
            if not output.is_relative_to(target.resolve()):
                raise RuntimeError("Invalid Python archive path")
            output.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, output.open("wb") as destination:
                shutil.copyfileobj(source, destination)


def prepare(root: Path = ROOT) -> dict:
    lock = json.loads((root / "installer/backend/python-runtime.lock.json").read_text())
    package = root / f"installer/cache/python.{lock['version']}.nupkg"
    package.parent.mkdir(parents=True, exist_ok=True)
    if not package.exists():
        urllib.request.urlretrieve(lock["url"], package)
    raw = package.read_bytes()
    if (hashlib.sha256(raw).hexdigest() != lock["sha256"] or
            base64.b64encode(hashlib.sha512(raw).digest()).decode() != lock["nuget_sha512"]):
        raise RuntimeError("Python package differs from pinned official NuGet package")
    target = (root / "runtime/installer-inputs/python312").resolve()
    parent = (root / "runtime/installer-inputs").resolve()
    if target.parent != parent:
        raise RuntimeError("Invalid staging directory")
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    extract_tools(package, target)
    executable = target / "python.exe"
    # No installation, registration or modification of the host Python.
    result = subprocess.run([str(executable), "-I", "-B", "-c",
        "import sys,struct,pip,venv,ensurepip; "
        "assert sys.version_info[:3]==(3,12,10) and struct.calcsize('P')==8"],
        capture_output=True, timeout=30)
    if result.returncode:
        raise RuntimeError("Packaged Python/pip/venv failed validation")
    signature = subprocess.run([shutil.which("pwsh.exe") or "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
        "$s=Get-AuthenticodeSignature -LiteralPath $env:NOVELIS_VERIFY_PYTHON; "
        "if ($s.Status -ne 'Valid' -or $s.SignerCertificate.Subject -notlike "
        "'*Python Software Foundation*') { exit 1 }"], capture_output=True,
        env=dict(os.environ, NOVELIS_VERIFY_PYTHON=str(executable)), timeout=120)
    if signature.returncode:
        raise RuntimeError("Official Python executable Authenticode verification failed")
    files = {p.relative_to(target).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(target.rglob("*")) if p.is_file()}
    manifest = {**lock, "schema_version": 1, "layout": "application-local",
                "system_registration": False, "files": files}
    (target / "runtime-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return {"version": lock["version"], "files": len(files), "sha256": lock["sha256"],
            "target": str(target), "authenticode": "valid_python_software_foundation"}


if __name__ == "__main__":
    print(json.dumps(prepare()))
