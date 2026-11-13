"""Compile a safe Inno fixture to reproduce and prevent late .env preparation."""
import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows Inno Setup")


@pytest.mark.parametrize("timing,custom,expected", [("late", False, False),
    ("before_run", False, True), ("before_run", True, True)])
def test_configuration_is_visible_to_run_before_backend_starts(tmp_path, timing, custom, expected):
    compiler = Path("C:/Program Files/Inno Setup 7/ISCC.exe")
    if not compiler.is_file():
        pytest.skip("Inno compiler unavailable")
    target = tmp_path / "installed app"
    env_file = tmp_path / "factory.env"
    db = r"C:\operator\configured.sqlite" if custom else ""
    env_file.write_text("CRYSTAL_REPORTS_PROGID=old.fixture\nNOVELIS_SQLITE_PATH=" + db + "\n")
    probe = tmp_path / "probe.ps1"
    probe.write_text(r'''$ErrorActionPreference='Stop'
$text=[IO.File]::ReadAllText((Join-Path (Get-Location) 'BACKEND\.env'))
$line=@($text -split "`r?`n" | Where-Object { $_ -like 'NOVELIS_SQLITE_PATH=*' })[0]
@{database_ready=($line -ne 'NOVELIS_SQLITE_PATH=');
  progid_ready=$text.Contains('CRYSTAL_REPORTS_PROGID=CrystalDesignRunTime.Application.11');
  preserved=$text.Contains('PRESERVED_FIXTURE=restored'); database=$line} |
  ConvertTo-Json | Set-Content result.json -Encoding UTF8
''')
    prerequisite = (ROOT / "installer/crystal/Prerequisite.iss").read_text(encoding="utf-8-sig")
    crystal_config = tmp_path / "crystal-config.iss"
    crystal_config.write_text(prerequisite[prerequisite.index("procedure SetCrystalProgId;"):], encoding="utf-8-sig")
    before = "PrepareBackendInstallation" if timing == "before_run" else "ResetBackendPreparation"
    event = "PrepareBackendInstallation;" if timing == "late" else ""
    harness = tmp_path / "configuration.iss"
    harness.write_text(f'''[Setup]
AppId=NovelisSyntheticConfiguration{timing}{custom}
AppName=Novelis configuration ordering fixture
AppVersion=1.0
DefaultDirName={target}
PrivilegesRequired=lowest
Uninstallable=no
DisableProgramGroupPage=yes
OutputDir={tmp_path}
OutputBaseFilename=configuration
[Files]
Source: "{env_file}"; DestDir: "{{app}}\\BACKEND"; DestName: ".env"
Source: "{probe}"; DestDir: "{{app}}"
[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{{app}}\\probe.ps1"""; WorkingDir: "{{app}}"; Flags: runhidden waituntilterminated; BeforeInstall: {before}
[Code]
function BackendIsPrepared: Boolean;
begin Result := True; end;
procedure ResetBackendPreparation;
begin end;
procedure MergeEnvAfterInstall(Dir: String);
begin SaveStringToFile(AddBackslash(Dir) + 'BACKEND\\.env', #13#10 + 'PRESERVED_FIXTURE=restored', True); end;
procedure SaveDacteInstallerInputs;
begin end;
#include "{crystal_config}"
#include "{ROOT / 'installer/backend/Hub.iss'}"
#include "{ROOT / 'installer/backend/Configuration.iss'}"
function InitializeSetup: Boolean;
begin WebViewPrepared := True; Result := True; end;
procedure CurStepChanged(CurStep: TSetupStep);
begin if CurStep = ssPostInstall then begin {event} end; end;
''', encoding="utf-8-sig")
    compiled = subprocess.run([str(compiler), str(harness)], capture_output=True, timeout=90)
    assert compiled.returncode == 0, compiled.stdout.decode(errors="replace")
    installed = subprocess.run([str(tmp_path / "configuration.exe"), "/VERYSILENT",
        "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-"], timeout=90)
    assert installed.returncode == 0
    result = json.loads((target / "result.json").read_text(encoding="utf-8-sig"))
    assert result["database_ready"] is expected
    assert result["progid_ready"] is expected
    assert result["preserved"] is expected
    if custom:
        assert result["database"] == "NOVELIS_SQLITE_PATH=" + db
    else:
        assert "NOVELIS_SQLITE_PATH=\\\\192.168.254.250" in (target / "BACKEND/.env").read_text(encoding="utf-8-sig")
    # Check the actual main installer binds the tested callback to bootstrap.
    script = (ROOT / "installer/AutomacaoNovelis.iss").read_text(encoding="utf-8-sig")
    assert "BeforeInstall: PrepareBackendInstallation; AfterInstall: VerifyBackendPreparation" in script
