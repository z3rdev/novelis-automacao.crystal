from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import get_legacy_config, get_settings_from_app
from app.config.legacy_config import LegacyConfig
from app.config.settings import Settings
from app.data.chamados_reader import read_chamados_payload


router = APIRouter(prefix="/chamados", tags=["chamados"])


@router.get("")
async def read_chamados(
    settings: Settings = Depends(get_settings_from_app),
    legacy_config: LegacyConfig = Depends(get_legacy_config),
) -> dict[str, Any]:
    workspace = settings.backend_root.parent
    novelis_config = legacy_config.novelis()
    report_path = novelis_config.get("relatorioCteXmlJsonFile")
    snapshot_path = novelis_config.get("chamadosSnapshotFile")
    return read_chamados_payload(workspace, report_path, snapshot_path)
