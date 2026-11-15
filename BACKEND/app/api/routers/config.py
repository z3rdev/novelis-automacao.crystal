from fastapi import APIRouter, Depends

from app.api.deps import get_env_catalog, get_settings_from_app, require_master_access
from app.config.env_catalog import EnvCatalog
from app.config.settings import Settings


router = APIRouter(prefix="/config", tags=["config"], dependencies=[Depends(require_master_access)])


@router.get("")
async def read_config(settings: Settings = Depends(get_settings_from_app)) -> dict[str, object]:
    return {
        "appName": settings.app_name,
        "environment": settings.app_env,
        "api": {
            "host": settings.api_host,
            "port": settings.api_port,
        },
        "browser": {
            "headless": settings.browser_headless,
            "width": settings.browser_width,
            "height": settings.browser_height,
            "playwrightPath": str(settings.browser_playwright_path),
            "downloadsDir": str(settings.browser_downloads_dir),
        },
        "paths": {
            "storageDir": str(settings.storage_dir),
            "stepsFile": str(settings.steps_file),
            "legacyProjectDir": str(settings.legacy_project_dir),
        },
        "prePasso": {
            "rodoparBrowserEnabled": settings.rodopar_browser_enabled,
            "url": settings.pre_url,
            "html5Url": settings.pre_html5_url,
            "rodoparUrl": settings.pre_html5_url,
            "stepDelayMs": settings.pre_step_delay_ms,
        },
    }


@router.get("/env")
async def read_env_catalog(catalog: EnvCatalog = Depends(get_env_catalog)) -> dict[str, object]:
    return catalog.grouped_public()
