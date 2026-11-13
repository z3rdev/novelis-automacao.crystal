"""Only application-owned Python processes may be stopped during uninstall."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(os.name != "nt" or not os.environ.get("NOVELIS_TEST_INSTALLED_HUB"), reason="Requires isolated Windows fixture")
def test_cleanup_stops_owned_interpreter_and_preserves_other_python(tmp_path):
    root = Path(os.environ["NOVELIS_TEST_INSTALLED_HUB"]).resolve()
    assert root.is_relative_to((ROOT / "runtime/crystal-tests").resolve())
    owned = subprocess.Popen([str(root / "runtime/python312/python.exe"), "-I", "-c", "import time; time.sleep(90)"])
    other = subprocess.Popen([sys.executable, "-I", "-c", "import time; time.sleep(90)"])
    harness = tmp_path / "cleanup.ps1"
    harness.write_text(r'''param($Source, $InstallRoot)
$ErrorActionPreference='Stop'
$tokens=$null; $errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($Source,[ref]$tokens,[ref]$errors)
$fn=$ast.Find({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Stop-OwnedBackendProcesses'},$true)
. ([scriptblock]::Create($fn.Extent.Text))
Stop-OwnedBackendProcesses $InstallRoot
''')
    try:
        result = subprocess.run([shutil.which("powershell.exe"), "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-File", str(harness),
            str(ROOT / "scripts/remove-desktop-service.ps1"), str(root)], capture_output=True, timeout=60)
        assert result.returncode == 0, result.stderr.decode(errors="replace")
        assert owned.wait(timeout=10) != 0
        assert other.poll() is None
    finally:
        for process in (owned, other):
            if process.poll() is None:
                subprocess.run(["taskkill.exe", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
            process.wait(timeout=15)
