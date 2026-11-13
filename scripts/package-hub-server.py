"""Package the local backend that accesses the shared SQLite database."""

import hashlib
import json
import runpy
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist/hub/NovelisCargoHub-BackendLocal-0.1.0.zip"


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    files = []
    for directory in ["BACKEND/app", "assets/reports", "installer/dacte"]:
        for path in (ROOT / directory).rglob("*"):
            if (path.is_file() and path.suffix not in {".pyc", ".pyo", ".log", ".tmp", ".bak"}
                    and not any(part.startswith(".") or part == "__pycache__" for part in path.relative_to(ROOT).parts)):
                files.append(path)
    for name in ["BACKEND/pyproject.toml", "INICIAR-BACKEND.cmd", "INICIAR-BACKEND-SERVIDOR.cmd", "scripts/bootstrap.ps1", "scripts/setup/bootstrap-state.ps1", "scripts/prepare-dacte.ps1",
                 "scripts/start-local-backend.ps1", "scripts/start-central-backend.ps1", "scripts/initialize-hub-store.py",
                 "docs/hub-tauri-local.md", "docs/hub-tauri-servidor.md", "docs/sefaz-documentos.md", "docs/dacte-installer.md",
                 "docs/crystal-dacte-api.md", "DESKTOP/automacao_novelis_desktop/config.py"]:
        files.append(ROOT / name)
    factory = runpy.run_path(str(ROOT / "scripts/prepare-installer-inputs.py"))["factory_environment"]
    example = factory((ROOT / "BACKEND/.env.example").read_text(encoding="utf-8-sig"))
    example = "\n".join(line for line in example.splitlines() if not line.startswith("NOVELIS_SQLITE_PATH="))
    example += "\nNOVELIS_SQLITE_PATH=\\\\192.168.254.250\\rede\\Publico\\novelis-automacao\\novelischamado.sqlite\n"
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as package:
        for path in sorted(files):
            package.write(path, path.relative_to(ROOT).as_posix())
        package.writestr("BACKEND/.env.example", example)
    result = {"package": str(OUTPUT), "files": len(files) + 1,
              "bytes": OUTPUT.stat().st_size, "sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
              "includes_credentials": False, "includes_vendor_runtimes": False}
    OUTPUT.with_suffix(".manifest.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
