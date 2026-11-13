import re
from datetime import datetime, timezone
from pathlib import Path

from app.config.settings import Settings


DEFAULT_CONFIRMATION_KEY = "rodopar-login"


def safe_confirmation_key(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or DEFAULT_CONFIRMATION_KEY).strip())
    return safe.strip("-") or DEFAULT_CONFIRMATION_KEY


def manual_confirmation_file(
    settings: Settings,
    run_id: str,
    key: str = DEFAULT_CONFIRMATION_KEY,
) -> Path:
    safe_run_id = safe_confirmation_key(run_id)
    safe_key = safe_confirmation_key(key)
    return settings.storage_dir / "manual-confirmations" / f"{safe_run_id}-{safe_key}.ok"


def reset_manual_confirmation(
    settings: Settings,
    run_id: str,
    key: str = DEFAULT_CONFIRMATION_KEY,
) -> None:
    manual_confirmation_file(settings, run_id, key).unlink(missing_ok=True)


def set_manual_confirmation(
    settings: Settings,
    run_id: str,
    key: str = DEFAULT_CONFIRMATION_KEY,
) -> Path:
    path = manual_confirmation_file(settings, run_id, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")
    return path


def consume_manual_confirmation(
    settings: Settings,
    run_id: str,
    key: str = DEFAULT_CONFIRMATION_KEY,
) -> bool:
    path = manual_confirmation_file(settings, run_id, key)
    if not path.exists():
        return False
    path.unlink(missing_ok=True)
    return True
