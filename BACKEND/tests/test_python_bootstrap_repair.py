"""Regression for an owned Python with installed MSI state but missing files."""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
POWERSHELL = shutil.which("powershell.exe")
pytestmark = pytest.mark.skipif(os.name != "nt" or not POWERSHELL, reason="Windows bootstrap")


@pytest.mark.parametrize("scenario,success,action,processes", [
    ("repair_success", True, "/repair", 1),
    ("repair_1603", False, "/repair", 1),
    ("zero_missing_files", False, "/repair", 1),
    ("zero_invalid_pip", False, "/repair", 1),
    ("install_success", True, "/quiet", 1),
    ("unowned_registration", False, None, 0),
    ("missing_pip_restored", True, "/repair", 1),
])
def test_python_bundle_action_and_file_preservation(tmp_path, scenario, success, action, processes):
    script = tmp_path / "bundle-contract.ps1"
    script.write_text(r'''param($Source, $TestRoot, $Scenario)
$ErrorActionPreference='Stop'
$tokens=$null; $errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($Source,[ref]$tokens,[ref]$errors)
foreach ($fn in $ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst]}, $true)) {
  . ([scriptblock]::Create($fn.Extent.Text))
}
$Root=$TestRoot
$RuntimeDir=Join-Path $Root 'runtime'
$LocalPythonDir=Join-Path $Root 'owned Python with spaces'
$LocalPythonExe=Join-Path $LocalPythonDir 'python.exe'
$EmbeddedPythonInstaller=Join-Path $Root 'fixture-installer.exe'
New-Item -ItemType Directory -Path $RuntimeDir,$LocalPythonDir -Force | Out-Null
Set-Content -LiteralPath $EmbeddedPythonInstaller -Value 'synthetic bundle'
$sentinel=Join-Path $LocalPythonDir 'keep-existing-files.txt'
Set-Content -LiteralPath $sentinel -Value 'preserve on success and failure'
$script:ProcessCalls=@()
$script:PipCalls=@()
$script:PipReady=($Scenario -notin @('zero_invalid_pip','missing_pip_restored'))
function Get-PythonRegistryInstallPath {
  if ($Scenario -eq 'install_success') { return '' }
  if ($Scenario -eq 'unowned_registration') { return (Join-Path $Root 'other-automacao-python') }
  return $LocalPythonDir + ''
}
function Assert-PythonInstaller { param($InstallerPath) }
function Test-PythonCommand { param($Candidate) return $true }
function Test-PythonBaseReady { param($Candidate) return $script:PipReady }
function Invoke-Checked {
  param($FilePath,$Arguments,$WorkingDirectory)
  $script:PipCalls += ,@($Arguments)
  if ($Scenario -eq 'zero_invalid_pip') { throw 'ensurepip fixture failure' }
  $script:PipReady=$true
  'synthetic pip output must not become the returned executable path'
}
function Start-Process {
  param($FilePath, $ArgumentList, $WindowStyle, [switch]$Wait, [switch]$PassThru)
  $script:ProcessCalls += ,@($ArgumentList)
  if ($Scenario -eq 'repair_1603') { return [pscustomobject]@{ExitCode=1603} }
  if ($Scenario -ne 'zero_missing_files') { Set-Content -LiteralPath $LocalPythonExe -Value 'fixture' }
  return [pscustomobject]@{ExitCode=0}
}
function Remove-Item { throw 'No Python directory may be removed by this flow.' }
$accepted=$false
$message=''
try { $returned=Install-LocalPython; $accepted=$true } catch { $message=[string]$_ }
[ordered]@{accepted=$accepted; message=$message; calls=$script:ProcessCalls;
  pip_calls=$script:PipCalls; returned=$returned;
  sentinel_preserved=(Test-Path -LiteralPath $sentinel)} |
  ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Root 'result.json') -Encoding UTF8
''', encoding="utf-8")
    result = subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
         str(script), str(ROOT / "scripts/bootstrap.ps1"), str(tmp_path), scenario],
        capture_output=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    state = json.loads((tmp_path / "result.json").read_text(encoding="utf-8-sig"))
    assert state["accepted"] is success
    assert state["sentinel_preserved"]
    assert len(state["calls"]) == processes
    if action:
        assert state["calls"][0][0] == action
        assert "/uninstall" not in state["calls"][0]
        assert "/norestart" in state["calls"][0]
        assert any(arg.startswith('TargetDir="') and "with spaces" in arg for arg in state["calls"][0])
    if scenario == "repair_1603":
        assert "1603" in state["message"]
    if scenario == "missing_pip_restored":
        assert state["pip_calls"] == [["-I", "-m", "ensurepip", "--upgrade", "--default-pip"]]
        assert state["returned"] == str(tmp_path / "owned Python with spaces/python.exe")


def test_changed_python_installer_is_rejected_before_execution(tmp_path):
    fixture = tmp_path / "python.exe"
    fixture.write_bytes(b"tampered fixture, never executable")
    script = tmp_path / "integrity.ps1"
    script.write_text(r'''param($Source, $InstallerPath)
$tokens=$null; $errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($Source,[ref]$tokens,[ref]$errors)
$fn=$ast.Find({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Assert-PythonInstaller'},$true)
. ([scriptblock]::Create($fn.Extent.Text))
try { Assert-PythonInstaller $InstallerPath; exit 0 } catch { exit 2 }
''')
    result = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
                             "Bypass", "-File", str(script),
                             str(ROOT / "scripts/bootstrap.ps1"), str(fixture)], timeout=60)
    assert result.returncode == 2


def test_real_missing_pip_is_restored_offline_in_owned_isolated_interpreter(tmp_path):
    owned = tmp_path / "owned Python without pip"
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(owned)], check=True, timeout=90)
    python = owned / "Scripts/python.exe"
    # Use a venv path layout in this fixture; ownership remains an exact directory.
    candidate_dir = python.parent
    before = subprocess.run([str(python), "-I", "-m", "pip", "--version"], capture_output=True)
    assert before.returncode != 0
    harness = tmp_path / "restore-pip.ps1"
    harness.write_text(r'''param($Source, $Candidate, $OwnedDirectory, $WorkingDirectory)
$ErrorActionPreference='Stop'
$tokens=$null; $errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($Source,[ref]$tokens,[ref]$errors)
foreach ($fn in $ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst]}, $true)) {
  . ([scriptblock]::Create($fn.Extent.Text))
}
$LocalPythonDir=$OwnedDirectory
$WheelhouseDir=$WorkingDirectory
$BackendDir=$WorkingDirectory
Restore-OwnedPythonPip $Candidate
Restore-OwnedPythonPip $Candidate
if (!(Test-PythonBaseReady $Candidate)) { exit 2 }
''')
    result = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
                             "Bypass", "-File", str(harness), str(ROOT / "scripts/bootstrap.ps1"),
                             str(python), str(candidate_dir), str(tmp_path)],
                            capture_output=True, timeout=180)
    assert result.returncode == 0, (result.stdout + result.stderr).decode(errors="replace")
    after = subprocess.run([str(python), "-I", "-m", "pip", "--version"], capture_output=True)
    assert after.returncode == 0
    assert str(owned).lower() in after.stdout.decode().lower()


def test_bootstrap_lock_waits_until_other_preparation_releases_file(tmp_path):
    harness = tmp_path / "lock.ps1"
    harness.write_text(r'''param($Source, $Runtime)
$ErrorActionPreference='Stop'
. $Source
$RuntimeDir=$Runtime
$lock=Enter-BootstrapLock -WaitSeconds 10
try { Set-Content -LiteralPath (Join-Path $RuntimeDir 'acquired.txt') -Value 'acquired' }
finally { $lock.Dispose() }
''')
    with (tmp_path / "bootstrap.lock").open("w"):
        process = subprocess.Popen([POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
                                    "Bypass", "-File", str(harness),
                                    str(ROOT / "scripts/setup/bootstrap-state.ps1"), str(tmp_path)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            time.sleep(1.5)
            assert not (tmp_path / "acquired.txt").exists()
            assert process.poll() is None
        except BaseException:
            process.kill()
            process.wait()
            raise
    stdout, stderr = process.communicate(timeout=20)
    assert process.returncode == 0, stderr.decode(errors="replace")
    assert (tmp_path / "acquired.txt").exists()
    assert "Aguardando" in stdout.decode(errors="replace")
