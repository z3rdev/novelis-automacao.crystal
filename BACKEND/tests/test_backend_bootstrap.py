"""Exercise bootstrap failure propagation without installing system prerequisites."""
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
POWERSHELL = shutil.which("powershell.exe")
pytestmark = pytest.mark.skipif(not POWERSHELL or os.name != "nt", reason="Windows bootstrap")


def run_ps(script, *arguments, env=None):
    return subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-File", str(script), *arguments],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
        timeout=90,
    )


def stage_bootstrap(tmp_path):
    root = tmp_path / "installed application with spaces"
    (root / "scripts/setup").mkdir(parents=True)
    (root / "BACKEND").mkdir()
    (root / "FRONTEND").mkdir()
    for relative in ("bootstrap.ps1", "setup/bootstrap-state.ps1"):
        shutil.copy2(ROOT / "scripts" / relative, root / "scripts" / relative)
    return root


def test_bootstrap_records_fresh_success_marker_and_log(tmp_path):
    root = stage_bootstrap(tmp_path)
    result = run_ps(root / "scripts/bootstrap.ps1", "-SkipBackend", "-SkipFrontend")
    assert result.returncode == 0, result.stdout + result.stderr
    state = json.loads((root / "runtime/bootstrap-result.json").read_text(encoding="utf-8-sig"))
    assert state["status"] == "succeeded"
    assert state["stage"] == "complete"
    assert state["exit_code"] == 0
    assert (root / "runtime/bootstrap-result.json.exitcode").read_text().strip() == "0"
    assert "complete" in (root / "runtime/bootstrap.log").read_text(encoding="utf-8-sig")


def test_failed_child_replaces_stale_success_with_failure_and_stage(tmp_path):
    root = stage_bootstrap(tmp_path)
    runtime = root / "runtime"
    runtime.mkdir()
    (runtime / "bootstrap-result.json.exitcode").write_text("0")
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    (fake_bin / "npm.cmd").write_text("@exit /b 23\n")
    env = dict(os.environ, PATH=str(fake_bin) + os.pathsep + os.environ["PATH"])
    result = run_ps(root / "scripts/bootstrap.ps1", "-SkipBackend", env=env)
    assert result.returncode == 1, result.stdout + result.stderr
    state = json.loads((runtime / "bootstrap-result.json").read_text(encoding="utf-8-sig"))
    assert state["status"] == "failed"
    assert state["stage"] == "frontend_dependencies"
    assert (runtime / "bootstrap-result.json.exitcode").read_text().strip() == "1"
    assert "Comando falhou" in (runtime / "bootstrap.log").read_text(encoding="utf-8-sig")


@pytest.mark.parametrize("response,expected", [("3.12:64", True), ("3.12:32", False),
                                                ("3.11:64", False), ("3.15:64", False)])
def test_offline_wheels_require_python_312_x64(tmp_path, response, expected):
    fake = tmp_path / "python fixture.cmd"
    fake.write_text(f"@echo {response}\n@exit /b 0\n")
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    harness = tmp_path / "check.ps1"
    # Load the function through PowerShell's parser, without running the installer.
    harness.write_text("""param($Source, $Candidate, $Wheels)
$tokens=$null; $errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($Source,[ref]$tokens,[ref]$errors)
$fn=$ast.Find({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Test-PythonCommand'},$true)
. ([scriptblock]::Create($fn.Extent.Text))
$WheelhouseDir=$Wheels
Test-PythonCommand $Candidate | ConvertTo-Json -Compress
""")
    result = run_ps(harness, str(ROOT / "scripts/bootstrap.ps1"), str(fake), str(wheels))
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout.strip()) is expected


def test_real_python_probe_preserves_python_code_quotes(tmp_path):
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    harness = tmp_path / "real-probe.ps1"
    harness.write_text("""param($Source, $Candidate, $Wheels)
$tokens=$null; $errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($Source,[ref]$tokens,[ref]$errors)
$fn=$ast.Find({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Test-PythonCommand'},$true)
. ([scriptblock]::Create($fn.Extent.Text))
$WheelhouseDir=$Wheels
Test-PythonCommand $Candidate | ConvertTo-Json -Compress
""")
    result = run_ps(harness, str(ROOT / "scripts/bootstrap.ps1"), sys.executable, str(wheels))
    assert result.returncode == 0, result.stdout + result.stderr
    import struct
    expected = sys.version_info[:2] == (3, 12) and struct.calcsize("P") == 8
    assert json.loads(result.stdout.strip()) is expected


def test_collect_only_preserves_scripts_and_excludes_private_configuration(tmp_path):
    root = tmp_path / "installed application"
    (root / "BACKEND").mkdir(parents=True)
    (root / "runtime").mkdir()
    (root / "scripts").mkdir()
    (root / ".automacao-novelis-install").write_text("fixture")
    (root / "BACKEND/pyproject.toml").write_text("[project]\nname='fixture'\n")
    secret = "SYNTHETIC_PRIVATE_CONFIG_DO_NOT_COLLECT"
    (root / "BACKEND/.env").write_text(secret)
    original_script = root / "scripts/bootstrap.ps1"
    original_script.write_text("# original script\n")
    (root / "runtime/python-install.log").write_text("installer exited but executable missing")
    (root / "runtime/python-installer-detail_001_core_JustForMe.log").write_text("synthetic child MSI log")
    result = run_ps(ROOT / "scripts/repair-backend.ps1", "-InstallationRoot", str(root), "-CollectOnly")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RECOVERY_STATUS=collected" in result.stdout
    assert original_script.read_text() == "# original script\n"
    archives = list((root / "runtime/backend-recovery").glob("*.zip"))
    assert len(archives) == 1
    with zipfile.ZipFile(archives[0]) as archive:
        assert any(name.endswith("before-python-install.log") for name in archive.namelist())
        assert any(name.endswith("after-python-installer-detail_001_core_JustForMe.log") for name in archive.namelist())
        assert all(".env" not in name for name in archive.namelist())
        assert all(secret.encode() not in archive.read(name) for name in archive.namelist())


def test_recovery_rejects_unidentified_installation_before_writing(tmp_path):
    root = tmp_path / "other application"
    root.mkdir()
    result = run_ps(ROOT / "scripts/repair-backend.ps1", "-InstallationRoot", str(root), "-CollectOnly")
    assert result.returncode != 0
    assert not (root / "runtime").exists()


@pytest.mark.parametrize("status", ["success", "failure", "crash"])
def test_compiled_inno_blocks_dependents_after_bootstrap_failure(tmp_path, status):
    compiler = Path("C:/Program Files/Inno Setup 7/ISCC.exe")
    if not compiler.exists():
        pytest.skip("Inno compiler unavailable")
    target = tmp_path / "target with spaces"
    bootstrap = tmp_path / "fixture.ps1"
    if status == "success":
        contents = """New-Item -ItemType Directory -Force 'BACKEND\\.venv\\Scripts' | Out-Null
Set-Content -LiteralPath 'BACKEND\\.venv\\Scripts\\python.exe' -Value 'fixture'
Set-Content -LiteralPath 'runtime\\bootstrap-result.json.exitcode' -Value '0'
exit 0
"""
    elif status == "failure":
        contents = "Set-Content -LiteralPath 'runtime\\bootstrap-result.json.exitcode' -Value '1'\nexit 1\n"
    else:
        contents = "exit 1\n"
    bootstrap.write_text(contents)
    (target / "runtime").mkdir(parents=True)
    (target / "runtime/bootstrap-result.json.exitcode").write_text("0")
    sentinel = tmp_path / "dependent.ps1"
    sentinel.write_text("Set-Content -LiteralPath 'dependent-ran.txt' -Value 'ran'\n")
    harness = tmp_path / "bootstrap-harness.iss"
    harness.write_text(f'''[Setup]
AppId=NovelisBootstrapSynthetic{status}
AppName=Bootstrap synthetic test
AppVersion=1.0
DefaultDirName={target}
PrivilegesRequired=lowest
Uninstallable=no
CreateAppDir=yes
DisableProgramGroupPage=yes
OutputDir={tmp_path}
OutputBaseFilename=bootstrap-harness
[Files]
Source: "{bootstrap}"; DestDir: "{{app}}"
Source: "{sentinel}"; DestDir: "{{app}}"
[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{{app}}\\fixture.ps1"""; WorkingDir: "{{app}}"; Flags: runhidden waituntilterminated; BeforeInstall: ResetBackendPreparation; AfterInstall: VerifyBackendPreparation
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{{app}}\\dependent.ps1"""; WorkingDir: "{{app}}"; Flags: runhidden waituntilterminated; Check: BackendIsPrepared
[Code]
#include "{ROOT / 'installer/backend/Preparation.iss'}"
''', encoding="utf-8-sig")
    compiled = subprocess.run([str(compiler), str(harness)], capture_output=True, timeout=90)
    assert compiled.returncode == 0, compiled.stdout.decode(errors="replace")
    installed = subprocess.run([str(tmp_path / "bootstrap-harness.exe"), "/VERYSILENT",
                                "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-"], timeout=90)
    assert installed.returncode == (0 if status == "success" else 20)
    assert (target / "dependent-ran.txt").exists() is (status == "success")
