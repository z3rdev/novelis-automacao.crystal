import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MANIFEST_NAMES = ("version.json", "manifest.json", "latest.json", "update.json")


@dataclass(frozen=True)
class UpdateInfo:
    update_id: str
    version: str
    source_dir: str
    target_path: str
    title: str
    notes: str


def check_for_update(root: Path, settings: dict[str, Any]) -> UpdateInfo | None:
    if not settings.get("update_enabled", True):
        return None
    source_dir = Path(str(settings.get("update_source_dir") or ""))
    if not source_dir.exists() or not source_dir.is_dir():
        return None
    installed = str(settings.get("app_version") or "").strip()
    manifest = _read_manifest(source_dir)
    info = _info_from_manifest(source_dir, manifest, installed) if manifest else _info_from_files(source_dir)
    if not info:
        return None
    state = _read_state(root)
    has_newer_version = bool(info.version and installed and _version_is_newer(info.version, installed))
    if state.get("last_seen_update_id") == info.update_id and not has_newer_version:
        return None
    return info


def mark_update_seen(root: Path, update_id: str) -> None:
    path = _state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"last_seen_update_id": update_id}, indent=2), encoding="utf-8")


def _info_from_manifest(source_dir: Path, manifest: dict[str, Any], installed: str) -> UpdateInfo | None:
    version = str(manifest.get("version") or manifest.get("build") or "").strip()
    update_id = str(manifest.get("id") or version or manifest.get("publishedAt") or "").strip()
    if version and installed and not _version_is_newer(version, installed):
        return None
    if not update_id:
        update_id = _newest_file_id(source_dir)
    if not update_id:
        return None
    target = _target_path(source_dir, manifest)
    return UpdateInfo(
        update_id=update_id,
        version=version or update_id,
        source_dir=str(source_dir),
        target_path=str(target),
        title=str(manifest.get("title") or "Nova atualização disponível"),
        notes=str(manifest.get("notes") or manifest.get("description") or ""),
    )


def _info_from_files(source_dir: Path) -> UpdateInfo | None:
    newest = _newest_file(source_dir)
    if not newest:
        return None
    update_id = f"{newest.name}:{int(newest.stat().st_mtime)}"
    return UpdateInfo(
        update_id=update_id,
        version="arquivo novo",
        source_dir=str(source_dir),
        target_path=str(source_dir),
        title="Nova atualização disponível",
        notes=f"Arquivo mais recente: {newest.name}",
    )


def _read_manifest(source_dir: Path) -> dict[str, Any]:
    for name in MANIFEST_NAMES:
        path = source_dir / name
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def _target_path(source_dir: Path, manifest: dict[str, Any]) -> Path:
    target = str(
        manifest.get("installer")
        or manifest.get("package")
        or manifest.get("file")
        or manifest.get("path")
        or ""
    ).strip()
    if not target:
        return source_dir
    path = Path(target)
    return path if path.is_absolute() else source_dir / path


def _newest_file_id(source_dir: Path) -> str:
    newest = _newest_file(source_dir)
    return f"{newest.name}:{int(newest.stat().st_mtime)}" if newest else ""


def _newest_file(source_dir: Path) -> Path | None:
    newest: Path | None = None
    newest_mtime = 0.0
    try:
        candidates = source_dir.rglob("*")
        for path in candidates:
            if not path.is_file() or path.name.lower() in MANIFEST_NAMES:
                continue
            mtime = path.stat().st_mtime
            if mtime > newest_mtime:
                newest = path
                newest_mtime = mtime
    except OSError:
        return None
    return newest


def _version_is_newer(remote: str, installed: str) -> bool:
    remote_parts = _version_parts(remote)
    installed_parts = _version_parts(installed)
    if remote_parts and installed_parts:
        return remote_parts > installed_parts
    return remote.strip() != installed.strip()


def _version_parts(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for token in str(value).replace("-", ".").split("."):
        digits = "".join(ch for ch in token if ch.isdigit())
        if digits:
            parts.append(int(digits))
    return tuple(parts)


def _read_state(root: Path) -> dict[str, Any]:
    path = _state_path(root)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _state_path(root: Path) -> Path:
    return root / "runtime" / "desktop-update-state.json"
