import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import APP_VERSION, config_path
from .env_file import env_paths

BUNDLE_KIND = "automacao-novelis-config-bundle"
STEPS_CATALOG_RELATIVE = Path("BACKEND") / "app" / "data" / "steps" / "pre_passo.json"


def export_config_bundle(root: Path, target_path: Path) -> dict[str, Any]:
    _, env_active = env_paths(root)
    bundle: dict[str, Any] = {
        "kind": BUNDLE_KIND,
        "appVersion": APP_VERSION,
        "exportedAt": datetime.now(timezone.utc).isoformat(),
        "env": env_active.read_text(encoding="utf-8") if env_active.exists() else "",
        "desktopSettings": _read_json(config_path(root)),
        "stepsCatalog": _read_json(root / STEPS_CATALOG_RELATIVE),
        "captureFiles": _collect_capture_files(root),
    }
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    return bundle


def import_config_bundle(root: Path, source_path: Path) -> list[str]:
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("kind") != BUNDLE_KIND:
        raise ValueError("Esse arquivo não é um pacote de configuração da Automação Novelis.")

    applied: list[str] = []

    env_text = payload.get("env")
    if isinstance(env_text, str) and env_text.strip():
        _, env_active = env_paths(root)
        env_active.parent.mkdir(parents=True, exist_ok=True)
        env_active.write_text(env_text, encoding="utf-8")
        applied.append(".env")

    desktop_settings = payload.get("desktopSettings")
    if isinstance(desktop_settings, dict):
        _write_json(config_path(root), desktop_settings)
        applied.append("desktop-settings.json")

    steps_catalog = payload.get("stepsCatalog")
    if isinstance(steps_catalog, dict):
        _write_json(root / STEPS_CATALOG_RELATIVE, steps_catalog)
        applied.append("pre_passo.json")

    capture_files = payload.get("captureFiles")
    if isinstance(capture_files, dict):
        for name, content in capture_files.items():
            safe_name = Path(str(name or "")).name
            if not safe_name or not isinstance(content, dict):
                continue
            _write_json(root / "captures" / safe_name, content)
            applied.append(f"captures/{safe_name}")

    return applied


def _collect_capture_files(root: Path) -> dict[str, Any]:
    captures_dir = root / "captures"
    result: dict[str, Any] = {}
    if not captures_dir.is_dir():
        return result
    for path in sorted(captures_dir.glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict) and isinstance(payload.get("points"), list):
            result[path.name] = payload
    return result


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
