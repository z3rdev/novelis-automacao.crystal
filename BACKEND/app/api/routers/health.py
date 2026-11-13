from datetime import datetime, timezone
from pathlib import Path
import re

from fastapi import APIRouter

from app.config.settings import get_settings


router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str | bool]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": "automacao-novelis-backend",
        "version": _read_app_version(settings.backend_root.parent),
        "backendRoot": str(settings.backend_root),
        "workspaceRoot": str(settings.backend_root.parent),
        "playwrightDriverOk": _playwright_driver_ok(settings.backend_root),
        "checkedAt": datetime.now(timezone.utc).isoformat(),
    }


def _read_app_version(root: Path) -> str:
    config_file = root / "DESKTOP" / "automacao_novelis_desktop" / "config.py"
    try:
        content = config_file.read_text(encoding="utf-8")
    except OSError:
        return ""
    match = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', content)
    return match.group(1) if match else ""


def _playwright_driver_ok(backend_root: Path) -> bool:
    driver_dir = backend_root / ".venv" / "Lib" / "site-packages" / "playwright" / "driver"
    return (driver_dir / "package" / "cli.js").exists() and (driver_dir / "node.exe").exists()
