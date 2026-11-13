from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_automation, get_settings_from_app
from app.config.settings import Settings
from app.domain.models import ManualConfirmationRequest, RunSnapshot, RunStartRequest
from app.services.automation_service import AutomationService
from app.services.manual_confirmation import safe_confirmation_key, set_manual_confirmation


router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("/current", response_model=RunSnapshot)
async def current_run(service: AutomationService = Depends(get_automation)) -> RunSnapshot:
    return await service.current()


@router.post("/start", response_model=RunSnapshot)
async def start_run(
    request: RunStartRequest,
    service: AutomationService = Depends(get_automation),
) -> RunSnapshot:
    try:
        return await service.start(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/stop", response_model=RunSnapshot)
async def stop_run(service: AutomationService = Depends(get_automation)) -> RunSnapshot:
    return await service.stop()


@router.post("/{run_id}/manual-confirmation")
async def confirm_manual_step(
    run_id: str,
    request: ManualConfirmationRequest,
    service: AutomationService = Depends(get_automation),
    settings: Settings = Depends(get_settings_from_app),
) -> dict[str, str]:
    snapshot = await service.current()
    if snapshot.id != run_id:
        raise HTTPException(status_code=404, detail="Execução ativa não encontrada para esta confirmação.")
    if snapshot.status not in {"running", "stopping"}:
        raise HTTPException(status_code=409, detail="Execução não está aguardando confirmação.")

    key = safe_confirmation_key(request.key)
    set_manual_confirmation(settings, run_id, key)
    return {"status": "confirmed", "run_id": run_id, "key": key}
