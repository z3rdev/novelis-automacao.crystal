"""Exercise the real PowerShell selector in dry-run mode; no process is killed."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows process inventory")


def test_updater_selects_installed_python_and_descendants_but_preserves_unrelated_apps(tmp_path):
    installed = tmp_path / "Cargo Hub"
    installed.mkdir()
    (installed / ".automacao-novelis-install").write_text("fixture")
    rows = [
        {"ProcessId": 501, "ParentProcessId": 0, "Name": "python.exe", "ExecutablePath": str(installed / "BACKEND/.venv/Scripts/python.exe"), "CommandLine": "python -m uvicorn app.main:app"},
        {"ProcessId": 502, "ParentProcessId": 0, "Name": "python.exe", "ExecutablePath": r"C:\Other\python.exe", "CommandLine": "python -m other_service --port 8000"},
        {"ProcessId": 503, "ParentProcessId": 501, "Name": "chrome.exe", "ExecutablePath": r"C:\Other\chrome.exe", "CommandLine": "chrome"},
        {"ProcessId": 504, "ParentProcessId": 0, "Name": "python.exe", "ExecutablePath": str(installed) + r"-other\python.exe", "CommandLine": "python unrelated"},
    ]
    inventory = tmp_path / "processes.json"
    inventory.write_text(json.dumps(rows), encoding="utf-8")
    harness = tmp_path / "dry-run.ps1"
    harness.write_text(r'''param($Script, $Root, $Inventory)
$ErrorActionPreference = 'Stop'
$global:FixtureInventory = $Inventory
function Get-CimInstance { param($ClassName)
  $rows = Get-Content -LiteralPath $global:FixtureInventory -Raw | ConvertFrom-Json
  foreach ($entry in $rows) { Write-Output -NoEnumerate $entry }
}
function Stop-Process { throw 'Dry-run must never terminate a process' }
function Stop-ScheduledTask { throw 'Dry-run must never stop a task' }
& $Script -InstallRoot $Root -DryRun
''', encoding="utf-8-sig")
    command = [shutil.which("powershell.exe"), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        "-File", str(harness), str(ROOT / "scripts/setup/stop-installed-stack.ps1"), str(installed), str(inventory)]
    result = subprocess.run(command, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert result.stdout.strip().startswith(b"{"), result.stdout.decode(errors="replace")
    payload = json.loads(result.stdout.decode("utf-8-sig"))
    assert payload["matched"] == 2
    assert payload["dry_run"] and not payload["unrelated_processes_stopped"]


def test_updater_rejects_unrecognized_installation_before_enumerating_or_killing(tmp_path):
    result = subprocess.run([shutil.which("powershell.exe"), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        "-File", str(ROOT / "scripts/setup/stop-installed-stack.ps1"), "-InstallRoot", str(tmp_path), "-DryRun"],
        capture_output=True, timeout=30)
    assert result.returncode != 0
    assert b"Encerramento cancelado" in result.stderr
