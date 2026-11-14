import asyncio

from fastapi import APIRouter, HTTPException, Request

from app.services.releases.config import DeveloperConfig
from app.services.releases.publisher import PublishRequest
from app.api.deps import require_operator_session as require_operator

router = APIRouter(prefix="/hub", tags=["cargo-hub-updates"])


@router.get("/developer")
def developer(request: Request):
    return DeveloperConfig(request.app.state.settings.backend_root).status()


@router.post("/developer/releases/test")
async def test_releases(request: Request):
    await require_operator(request)
    config = DeveloperConfig(request.app.state.settings.backend_root)
    if not config.enabled():
        raise HTTPException(403, "Modo desenvolvedor desativado.")
    return await asyncio.to_thread(config.probe)


@router.get("/developer/releases/publish")
async def publish_status(request: Request):
    await require_operator(request)
    if not DeveloperConfig(request.app.state.settings.backend_root).enabled():
        raise HTTPException(403, "Modo desenvolvedor desativado.")
    return request.app.state.release_publisher.snapshot()


@router.post("/developer/releases/publish", status_code=202)
async def publish_release(body: PublishRequest, request: Request):
    await require_operator(request)
    try:
        return request.app.state.release_publisher.start(body)
    except PermissionError:
        raise HTTPException(403, "Modo desenvolvedor desativado.") from None
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None


@router.get("/updates")
def update_status(request: Request):
    return request.app.state.releases.snapshot()


@router.post("/updates/check")
async def check_updates(request: Request):
    return await request.app.state.releases.check()


@router.post("/updates/download", status_code=202)
async def download_update(request: Request):
    await require_operator(request)
    try:
        return request.app.state.releases.start_download()
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None


@router.post("/updates/install", status_code=202)
async def install_update(request: Request):
    await require_operator(request)
    snapshot = await request.app.state.automation.current()
    if snapshot.status in {"running", "stopping"}:
        raise HTTPException(409, "Aguarde a automação encerrar antes de instalar a atualização.")
    try:
        return await request.app.state.releases.install()
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
