"""An isolated, disposable Chromium profile for Windows client-certificate selection."""

import json
import shutil
import tempfile
from pathlib import Path

from app.services.sefaz_certificate import certificate_rule


def create_profile(root: Path, certificate: dict) -> Path:
    root = root.resolve() / "browser-profiles"
    root.mkdir(parents=True, exist_ok=True)
    profile = Path(tempfile.mkdtemp(prefix="sefaz-", dir=root))
    default = profile / "Default"
    default.mkdir()
    # Chromium's content-settings provider reads this list of stringified rules.
    # A dedicated profile avoids changing the workstation's managed policies.
    preferences = {"profile": {"managed_auto_select_certificate_for_urls": [
        json.dumps(certificate_rule(certificate), ensure_ascii=False),
    ]}}
    (default / "Preferences").write_text(json.dumps(preferences, ensure_ascii=False), encoding="utf-8")
    return profile


def remove_profile(root: Path, profile: Path) -> None:
    base = root.resolve() / "browser-profiles"
    resolved = profile.resolve()
    if resolved.parent != base or not resolved.name.startswith("sefaz-"):
        raise ValueError("Perfil de navegador fora da pasta de trabalho esperada.")
    shutil.rmtree(resolved, ignore_errors=True)
