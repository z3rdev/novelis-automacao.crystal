from fastapi import APIRouter, Depends

from app.api.deps import get_settings_from_app
from app.config.settings import Settings
from app.domain.models import FlowDefinition
from app.services.flow_catalog import list_flows


router = APIRouter(prefix="/flows", tags=["flows"])


@router.get("", response_model=list[FlowDefinition])
async def flows(settings: Settings = Depends(get_settings_from_app)) -> list[FlowDefinition]:
    return list_flows(settings.rodopar_browser_enabled)
