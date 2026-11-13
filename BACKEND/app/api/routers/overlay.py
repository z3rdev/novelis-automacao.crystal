from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_automation
from app.services.automation_service import AutomationService
from app.services.overlay_bridge import (
    get_overlay_state,
    peek_overlay_paused,
    push_overlay_command,
    set_overlay_paused,
)


router = APIRouter(prefix="/runs", tags=["overlay"])


def _default_state() -> dict[str, Any]:
    return {
        "status": "",
        "captureFile": "",
        "currentStep": None,
        "currentLabel": "",
        "recording": False,
        "points": [],
    }


@router.get("/{run_id}/overlay/state")
async def overlay_state(run_id: str) -> dict[str, Any]:
    state = get_overlay_state(run_id) or _default_state()
    return {**state, "paused": peek_overlay_paused(run_id)}


@router.post("/{run_id}/overlay/command")
async def overlay_command(
    run_id: str,
    command: dict[str, Any],
    service: AutomationService = Depends(get_automation),
) -> dict[str, str]:
    snapshot = await service.current()
    if snapshot.id != run_id:
        raise HTTPException(status_code=404, detail="Execução ativa não encontrada para este comando.")
    if snapshot.status not in {"running", "stopping"}:
        raise HTTPException(status_code=409, detail="Execução não está aguardando comandos do overlay.")

    # "pause"/"resume" only ever toggled the paused flag directly in the old injected-JS
    # overlay (RodoparReplayOverlay never had a dispatch branch for those action types),
    # so they bypass the one-shot command queue here too. Every other command type used
    # to clear the paused flag client-side as a blanket rule before pushing the action —
    # replicated here so a stale pause never lingers after e.g. clicking Salvar.
    command_type = str(command.get("type") or "").lower()
    if command_type == "pause":
        set_overlay_paused(run_id, True)
        return {"status": "queued", "run_id": run_id}
    if command_type == "resume":
        set_overlay_paused(run_id, False)
        return {"status": "queued", "run_id": run_id}
    if command_type in {"start_recording", "stop_recording"}:
        # Toggling the click recorder must not resume a paused run — the whole point is to
        # capture extra points while everything else stays frozen.
        push_overlay_command(run_id, command)
        return {"status": "queued", "run_id": run_id}

    set_overlay_paused(run_id, False)
    push_overlay_command(run_id, command)
    return {"status": "queued", "run_id": run_id}
