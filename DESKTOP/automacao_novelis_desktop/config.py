import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any


DEFAULT_WEEKDAYS = [0, 1, 2, 3, 4]
APP_VERSION = "0.1.36"
DEFAULT_UPDATE_SOURCE_DIR = (
    "\\\\192.168.254.250\\rede\\Publico\\AUTOMA\u00c7\u00c3O-CTE\\ATUALIZACOES\\ATUALIZACAO-NOVELIS"
)


def project_root_from_file(file_path: str) -> Path:
    return Path(file_path).resolve().parents[2]


def runtime_dir(root: Path) -> Path:
    path = root / "runtime"
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path(root: Path) -> Path:
    return runtime_dir(root) / "desktop-settings.json"


def default_settings() -> dict[str, Any]:
    password = os.environ.get("AUTOMACAO_NOVELIS_SETUP_PASSWORD", "admin")
    return {
        "backend_url": "http://127.0.0.1:8000/api",
        "frontend_url": "http://127.0.0.1:5173",
        "app_version": APP_VERSION,
        "auto_run_enabled": False,
        "auto_consult_enabled": False,
        "update_enabled": True,
        "update_source_dir": DEFAULT_UPDATE_SOURCE_DIR,
        "update_check_interval_seconds": 20,
        "start_time": "08:00",
        "weekdays": DEFAULT_WEEKDAYS,
        "start_delay_minutes": 0,
        "automation_interval_minutes": 0,
        "consult_interval_minutes": 0,
        "last_auto_run_date": "",
        "last_auto_run_at": "",
        "last_consult_at": "",
        "last_auto_run_status": "",
        "password": make_password_record(password),
    }


def load_settings(root: Path) -> dict[str, Any]:
    path = config_path(root)
    if not path.exists():
        settings = default_settings()
        save_settings(root, settings)
        return settings
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        loaded = {}
    settings = default_settings()
    settings.update({key: value for key, value in loaded.items() if key not in {"password", "app_version"}})
    if isinstance(loaded.get("password"), dict):
        settings["password"] = loaded["password"]
    return settings


def save_settings(root: Path, settings: dict[str, Any]) -> None:
    path = config_path(root)
    path.write_text(json.dumps(settings, indent=2, ensure_ascii=True), encoding="utf-8")


def make_password_record(password: str) -> dict[str, str]:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return {
        "salt": base64.b64encode(salt).decode("ascii"),
        "hash": base64.b64encode(digest).decode("ascii"),
    }


def verify_password(settings: dict[str, Any], password: str) -> bool:
    record = settings.get("password") or {}
    try:
        salt = base64.b64decode(record.get("salt", ""))
        expected = base64.b64decode(record.get("hash", ""))
    except Exception:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return hmac.compare_digest(digest, expected)


def set_password(settings: dict[str, Any], password: str) -> None:
    settings["password"] = make_password_record(password)
