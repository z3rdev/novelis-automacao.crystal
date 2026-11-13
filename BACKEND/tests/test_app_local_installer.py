"""Validate isolation and rejection of malformed application-local runtime inputs."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_python_archive_rejects_escape_and_preserves_complete_tools(tmp_path):
    module = load_script("prepare-python-runtime")
    archive = tmp_path / "python.nupkg"
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr("tools/LICENSE.txt", "fixture license")
        package.writestr("tools/Lib/venv/__init__.py", "fixture")
        package.writestr("tools/../../outside.txt", "escape")
    with pytest.raises(RuntimeError, match="Invalid Python archive path"):
        module.extract_tools(archive, tmp_path / "output")
    assert not (tmp_path / "outside.txt").exists()
    assert (tmp_path / "output/LICENSE.txt").read_text() == "fixture license"


@pytest.mark.skipif(os.name != "nt", reason="Windows bootstrap")
@pytest.mark.parametrize("scenario", ["missing_manifest", "wrong_version", "missing_file", "changed_file"])
def test_installed_mode_rejects_invalid_runtime_without_global_fallback(tmp_path, scenario):
    root = tmp_path / "installed app"
    python = root / "runtime/python312"
    python.mkdir(parents=True)
    manifest = json.loads((ROOT / "installer/backend/python-runtime.lock.json").read_text())
    manifest["files"] = {"python.exe": "0" * 64}
    if scenario == "wrong_version":
        manifest["version"] = "3.15.0"
    if scenario != "missing_manifest":
        (python / "runtime-manifest.json").write_text(json.dumps(manifest))
    if scenario == "changed_file":
        (python / "python.exe").write_text("fixture changed bytes")
    harness = tmp_path / "probe.ps1"
    harness.write_text(r'''param($Helper, $Root)
$ErrorActionPreference='Stop'
. $Helper
function Test-PythonBaseReady { throw 'Global Python must never be consulted' }
try { Resolve-AppLocalPython; exit 0 } catch { Write-Output $_.Exception.Message; exit 2 }
''')
    result = subprocess.run([shutil.which("powershell.exe"), "-NoProfile", "-NonInteractive",
        "-ExecutionPolicy", "Bypass", "-File", str(harness), str(ROOT / "scripts/setup/app-local-python.ps1"),
        str(root)], capture_output=True, timeout=60)
    assert result.returncode == 2, result.stderr.decode(errors="replace")
    assert b"Global Python" not in result.stdout


@pytest.mark.skipif(os.name != "nt", reason="Inno Setup Windows")
@pytest.mark.parametrize("webview_ready,expected", [(True, 0), (False, 21)])
def test_compiled_hub_setup_blocks_open_when_webview_fails(tmp_path, webview_ready, expected):
    compiler = Path("C:/Program Files/Inno Setup 7/ISCC.exe")
    if not compiler.is_file():
        pytest.skip("Inno compiler unavailable")
    target = tmp_path / "target"
    (target / "runtime").mkdir(parents=True)
    # Stale success must never mask this run's missing/failing completion marker.
    (target / "runtime/webview2-result.exitcode").write_text("0")
    fixture = tmp_path / "fixture.ps1"
    fixture.write_text("Set-Content runtime\\webview2-result.exitcode 0\n" if webview_ready else "exit 1\n")
    dependent = tmp_path / "open.ps1"
    dependent.write_text("Set-Content opened.txt yes\n")
    harness = tmp_path / "harness.iss"
    harness.write_text(f'''[Setup]
AppId=HubSyntheticWebView{webview_ready}
AppName=Hub WebView synthetic test
AppVersion=1.0
DefaultDirName={target}
PrivilegesRequired=lowest
Uninstallable=no
DisableProgramGroupPage=yes
OutputDir={tmp_path}
OutputBaseFilename=harness
[Files]
Source: "{fixture}"; DestDir: "{{app}}"
Source: "{dependent}"; DestDir: "{{app}}"
[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{{app}}\\fixture.ps1"""; WorkingDir: "{{app}}"; Flags: runhidden waituntilterminated; BeforeInstall: ResetWebViewPreparation; AfterInstall: VerifyWebViewPreparation
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{{app}}\\open.ps1"""; WorkingDir: "{{app}}"; Flags: runhidden waituntilterminated; Check: HubIsPrepared
[Code]
function BackendIsPrepared: Boolean;
begin
  Result := True;
end;
#include "{ROOT / 'installer/backend/Hub.iss'}"
''', encoding="utf-8-sig")
    compiled = subprocess.run([str(compiler), str(harness)], capture_output=True, timeout=90)
    assert compiled.returncode == 0, compiled.stdout.decode(errors="replace")
    installed = subprocess.run([str(tmp_path / "harness.exe"), "/VERYSILENT", "/SUPPRESSMSGBOXES",
        "/NORESTART", "/SP-"], timeout=90)
    assert installed.returncode == expected
    assert (target / "opened.txt").exists() is webview_ready


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell output encoding")
def test_playwright_probe_accepts_browser_under_accented_path(tmp_path):
    cache = ROOT / "ms-playwright"
    if not list(cache.glob("chromium-*/chrome-win64/chrome.exe")):
        pytest.skip("Bundled Chromium unavailable")
    accented = tmp_path / "Aplicação com acentuação"
    accented.mkdir()
    browsers = accented / "ms-playwright"
    subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(browsers), str(cache)],
        check=True, capture_output=True)
    harness = tmp_path / "browser-probe.ps1"
    harness.write_text(r'''param($Source, $Python, $Browsers)
$ErrorActionPreference='Stop'
$tokens=$null; $errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($Source,[ref]$tokens,[ref]$errors)
$fn=$ast.Find({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Test-PlaywrightChromium'},$true)
. ([scriptblock]::Create($fn.Extent.Text))
$VenvPythonExe=$Python
$PlaywrightPath=$Browsers
$env:PLAYWRIGHT_BROWSERS_PATH=$Browsers
Test-PlaywrightChromium | ConvertTo-Json -Compress
''')
    result = subprocess.run([shutil.which("powershell.exe"), "-NoProfile", "-NonInteractive",
        "-ExecutionPolicy", "Bypass", "-File", str(harness), str(ROOT / "scripts/bootstrap.ps1"),
        sys.executable, str(browsers)], capture_output=True, timeout=90)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert json.loads(result.stdout.strip()) is True
