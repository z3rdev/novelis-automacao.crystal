"""Private profiles carry operator data explicitly, without leaking values in reports."""
import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def module():
    spec = importlib.util.spec_from_file_location("environment_payload", ROOT / "scripts/setup/environment_payload.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    return helper


def test_private_profile_fills_credentials_retains_new_defaults_and_exact_paths():
    helper = module()
    secret = "synthetic-pass # $ \\\\ ' special"
    raw = "CONSULTA_DB_SERVER=private-server\nCONSULTA_DB_PASS=" + secret + "\nNETWORK=\\\\fixture\\dados\n"
    text, keys = helper.compose("CONSULTA_DB_SERVER=\nCONSULTA_DB_PASS=\nNEW_SETTING=true\n", raw)
    parsed = helper.assignments(text)
    assert parsed["CONSULTA_DB_PASS"] == secret
    assert parsed["NETWORK"] == r"\\fixture\dados"
    assert parsed["NEW_SETTING"] == "true"
    assert parsed["CRYSTAL_REPORTS_PROGID"] == "CrystalDesignRunTime.Application.11"
    assert parsed["CRYSTAL_CODE128_PROVIDER"] == "python"
    assert "CRYSTAL_CODE128_PROVIDER" in keys
    assert "CONSULTA_DB_PASS" in keys


@pytest.mark.parametrize("key", ["PIDKEY", "KEY", "SN", "CRYSTAL_LICENSE_KEY"])
def test_license_values_are_rejected_without_echoing_them(key):
    helper = module()
    secret = "SYNTHETIC_LICENSE_DO_NOT_LOG"
    with pytest.raises(ValueError) as error:
        helper.compose("DEFAULT=true\n", key + "=" + secret)
    assert secret not in str(error.value)


def test_private_staging_reports_only_counts_and_requires_explicit_source(tmp_path):
    helper = module()
    source = tmp_path / "authorized.env"
    secret = "SYNTHETIC_PRIVATE_DATABASE_PASSWORD"
    source.write_text("CONSULTA_DB_PASS=" + secret + "\n")
    calls = []
    report = helper.stage(tmp_path, "CONSULTA_DB_PASS=\n", source, lambda path: calls.append(path))
    target = tmp_path / "runtime/installer-inputs/private-configuration"
    assert secret in (target / "BACKEND.env").read_text()
    assert calls == [target, target]
    assert secret not in json.dumps(report)
    assert secret not in (target / "profile.keys").read_text()
    assert helper.stage(tmp_path, "CONSULTA_DB_PASS=\n", None, lambda _: None) == {"included": False}
    assert not (target / "BACKEND.env").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows Inno Setup")
def test_private_installer_replaces_empty_and_stale_profile_fields_preserves_local_values(tmp_path):
    compiler = Path("C:/Program Files/Inno Setup 7/ISCC.exe")
    if not compiler.is_file():
        pytest.skip("Inno compiler unavailable")
    target = tmp_path / "installed operator app"
    (target / "BACKEND").mkdir(parents=True)
    secret = "SYNTHETIC_PROFILE_PASSWORD"
    (target / "BACKEND/.env").write_text("CONSULTA_DB_SERVER=\nCONSULTA_DB_PASS=\nMODE=stale\nLOCAL_PRINTER=operator\n")
    seed = tmp_path / "seed.env"
    seed.write_text("CONSULTA_DB_SERVER=configured\nCONSULTA_DB_PASS=" + secret + "\nMODE=correct\nLOCAL_PRINTER=default\nNOVELIS_SQLITE_PATH=\n")
    keys = tmp_path / "profile.keys"
    keys.write_text("CONSULTA_DB_SERVER\nCONSULTA_DB_PASS\nMODE\n")
    main = (ROOT / "installer/AutomacaoNovelis.iss").read_text(encoding="utf-8-sig")
    merge = tmp_path / "merge.iss"
    merge.write_text(main[main.index("function EnvFilePath("):main.index("function InstalledMarkerPath(")], encoding="utf-8-sig")
    prereq = (ROOT / "installer/crystal/Prerequisite.iss").read_text(encoding="utf-8-sig")
    crystal = tmp_path / "crystal.iss"
    crystal.write_text(prereq[prereq.index("procedure SetCrystalProgId;"):], encoding="utf-8-sig")
    probe = tmp_path / "probe.ps1"
    probe.write_text(r'''$ErrorActionPreference='Stop'
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Security') -ErrorAction Stop
$file=Join-Path (Get-Location) 'BACKEND\.env'
$text=[IO.File]::ReadAllText($file)
$acl=Get-Acl -LiteralPath $file
@{server=$text.Contains('CONSULTA_DB_SERVER=configured');
 password=$text.Contains('CONSULTA_DB_PASS=SYNTHETIC_PROFILE_PASSWORD');
 mode=$text.Contains('MODE=correct'); local=$text.Contains('LOCAL_PRINTER=operator');
 private_acl=$acl.AreAccessRulesProtected} | ConvertTo-Json | Set-Content result.json -Encoding UTF8
''')
    harness = tmp_path / "private.iss"
    harness.write_text(f'''#define PrivateConfiguration
[Setup]
AppId=NovelisPrivateConfigSynthetic
AppName=Private configuration fixture
AppVersion=1.0
DefaultDirName={target}
PrivilegesRequired=lowest
Uninstallable=no
DisableProgramGroupPage=yes
OutputDir={tmp_path}
OutputBaseFilename=private
[Files]
Source: "{seed}"; DestDir: "{{app}}\\BACKEND"; DestName: ".env"; Flags: ignoreversion
Source: "{keys}"; DestDir: "{{app}}\\installer-cache\\configuration"
Source: "{ROOT / 'scripts/setup/protect-operational-env.ps1'}"; DestDir: "{{app}}\\scripts\\setup"
Source: "{probe}"; DestDir: "{{app}}"
[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{{app}}\\probe.ps1"""; WorkingDir: "{{app}}"; Flags: runhidden waituntilterminated; BeforeInstall: PrepareBackendInstallation
[Code]
var EnvBackupLines: TStringList;
function BackendIsPrepared: Boolean; begin Result := True; end;
procedure ResetBackendPreparation; begin end;
procedure SaveDacteInstallerInputs; begin end;
#include "{ROOT / 'installer/backend/OperationalConfiguration.iss'}"
#include "{merge}"
#include "{crystal}"
#include "{ROOT / 'installer/backend/Hub.iss'}"
#include "{ROOT / 'installer/backend/Configuration.iss'}"
function InitializeSetup: Boolean;
begin WebViewPrepared := True; Result := True; end;
function PrepareToInstall(var NeedsRestart: Boolean): String;
begin BackupExistingEnv(ExpandConstant('{{app}}')); Result := ''; end;
''', encoding="utf-8-sig")
    compiled = subprocess.run([str(compiler), str(harness)], capture_output=True, timeout=90)
    assert compiled.returncode == 0, compiled.stdout.decode(errors="replace")
    install_log = tmp_path / "install.log"
    result = subprocess.run([str(tmp_path / "private.exe"), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-", "/LOG=" + str(install_log)], timeout=90)
    assert result.returncode == 0
    assert (target / "result.json").is_file(), install_log.read_text(encoding="utf-8-sig", errors="replace")[-3000:]
    checks = json.loads((target / "result.json").read_text(encoding="utf-8-sig"))
    assert all(checks.values()), checks
