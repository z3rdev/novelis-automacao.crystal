from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_settings_from_app
from app.config.settings import Settings
from app.infrastructure.json_store import write_json

router = APIRouter(prefix="/capture-files", tags=["capture-files"])


@router.post("/import")
async def import_capture_file(
    payload: dict[str, Any],
    settings: Settings = Depends(get_settings_from_app),
) -> dict[str, str]:
    raw_path = str(payload.get("path") or "").strip()
    content = payload.get("content")
    if not raw_path:
        raise HTTPException(status_code=400, detail="Informe o caminho do arquivo de captura.")
    if not isinstance(content, dict) or not isinstance(content.get("points"), list):
        raise HTTPException(status_code=400, detail="O JSON precisa ter uma lista \"points\".")

    workspace = settings.backend_root.parent
    target = _resolve_within_captures(raw_path, workspace)
    write_json(target, content)
    return {"status": "imported", "path": str(target), "totalPoints": str(len(content["points"]))}


def _resolve_within_captures(raw_path: str, workspace: Path) -> Path:
    path = Path(raw_path)
    target = path if path.is_absolute() else workspace / path
    target = target.resolve(strict=False)
    captures_root = (workspace / "captures").resolve(strict=False)
    if captures_root not in target.parents and target != captures_root:
        raise HTTPException(status_code=400, detail="O arquivo de captura precisa ficar dentro de captures/.")
    return target
