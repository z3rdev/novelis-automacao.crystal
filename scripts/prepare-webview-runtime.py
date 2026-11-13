"""Cache Microsoft's complete Evergreen x64 installer, with its signed identity."""
import hashlib
import json
import os
import shutil
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "https://go.microsoft.com/fwlink/p/?LinkId=2124701"


def prepare():
    package = ROOT / "installer/cache/MicrosoftEdgeWebView2RuntimeInstallerX64.exe"
    if not package.is_file():
        package.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(URL, package)
    result = subprocess.run([shutil.which("pwsh.exe") or "powershell.exe", "-NoProfile", "-NonInteractive",
        "-Command", "$s=Get-AuthenticodeSignature -LiteralPath $env:NOVELIS_WEBVIEW; "
        "if ($s.Status -ne 'Valid' -or $s.SignerCertificate.Subject -notlike '*Microsoft Corporation*') { exit 1 }"],
        env=dict(os.environ, NOVELIS_WEBVIEW=str(package)), timeout=120)
    if result.returncode:
        raise RuntimeError("WebView2 installer signature is not valid Microsoft Corporation")
    target = ROOT / "runtime/installer-inputs/webview2"
    target.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(package, target / package.name)
    manifest = {"filename": package.name, "url": URL, "bytes": package.stat().st_size,
                "sha256": hashlib.sha256(package.read_bytes()).hexdigest(), "signature": "valid_microsoft"}
    (target / "webview2.manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest))


if __name__ == "__main__":
    prepare()
