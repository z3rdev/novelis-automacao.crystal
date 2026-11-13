"""Exercise offline installed-mode preparation in a new directory, without installing Crystal."""
import datetime
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    target = ROOT / f"runtime/crystal-tests/hub-offline-{stamp}/Novelis Cargo Hub"
    target.mkdir(parents=True)
    for source, destination in [
        ("BACKEND/app", "BACKEND/app"), ("scripts", "scripts"),
        ("DESKTOP", "DESKTOP"), ("assets/reports", "assets/reports"),
        ("FRONTEND-HUB/dist-desktop", "FRONTEND-HUB/dist-desktop"),
        ("runtime/installer-inputs/python312", "runtime/python312"),
        ("runtime/installer-inputs/wheels", "installer-cache/wheels"),
    ]:
        shutil.copytree(ROOT / source, target / destination,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".env", ".env.*"))
    shutil.copy2(ROOT / "BACKEND/pyproject.toml", target / "BACKEND/pyproject.toml")
    shutil.copy2(ROOT / "installer/.automacao-novelis-install", target / ".automacao-novelis-install")
    # Browser bytes were validated separately by the build. No installer is executed on this host.
    subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(target / "ms-playwright"),
                    str(ROOT / "ms-playwright")], check=True, capture_output=True)
    database = target / "runtime/isolated.sqlite"
    environment = dict(os.environ, NOVELIS_SQLITE_PATH=str(database), PIP_NO_INDEX="1",
        PIP_CONFIG_FILE=os.devnull, PYTHONHOME="Z:\\missing-python", PYTHONPATH="Z:\\missing-modules",
        PATH=os.pathsep.join([str(Path(os.environ["WINDIR"]) / "System32"),
                             str(Path(os.environ["WINDIR"]) / "System32/WindowsPowerShell/v1.0")]))
    command = [str(Path(os.environ["WINDIR"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"),
               "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
               str(target / "scripts/bootstrap.ps1"), "-SkipFrontend"]
    with (target.parent / "offline-bootstrap.log").open("wb") as log:
        result = subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT, timeout=600)
    state_file = target / "runtime/bootstrap-result.json"
    state = json.loads(state_file.read_text(encoding="utf-8-sig")) if state_file.exists() else {}
    readiness_path = target / "runtime/backend-readiness.json"
    readiness = json.loads(readiness_path.read_text()) if readiness_path.exists() else {}
    evidence = {"root": str(target), "exit_code": result.returncode, "bootstrap": state,
        "readiness": readiness, "python_system_installation_executed": False,
        "crystal_installation_executed": False, "browser_fixture": "junction_to_official_bundled_chromium",
        "database": "isolated_local_sqlite", "clean_machine_homologation": False,
        "frontend_index_sha256": hashlib.sha256((target / "FRONTEND-HUB/dist-desktop/index.html").read_bytes()).hexdigest()}
    (target.parent / "verification.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence))
    if result.returncode or state.get("status") != "succeeded" or readiness.get("hub_api") is not True:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
