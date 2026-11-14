import asyncio
import sqlite3

from fastapi import APIRouter, HTTPException, Request

from app.api.deps import require_operator_session
from app.domain.hub_features import NotificationInput, ScheduleInput
from app.services.developer_monitor import snapshot as monitor_snapshot
from app.services.releases.config import DeveloperConfig

router = APIRouter(prefix="/hub", tags=["notifications-and-schedules"])


def notifications(request: Request):
    service = request.app.state.notifications
    if service is None or not service.store.ready:
        raise HTTPException(503, "Configure o cache e os registros de leitura das notificações.")
    return service


def scheduler(request: Request):
    service = request.app.state.scheduler
    if service is None or not service.repository.store.ready:
        raise HTTPException(503, "Configure o banco compartilhado para os agendamentos.")
    return service


async def developer(request: Request) -> dict:
    actor = await require_operator_session(request)
    if not DeveloperConfig(request.app.state.settings.backend_root).enabled():
        raise HTTPException(403, "Modo desenvolvedor desativado.")
    return actor


@router.get("/developer/monitor")
async def developer_monitor(request: Request):
    await developer(request)
    try:
        return await asyncio.to_thread(monitor_snapshot, request.app.state.session_audit)
    except (OSError, RuntimeError, sqlite3.Error):
        raise HTTPException(503, "Não foi possível consultar o registro compartilhado de usuários e dispositivos.") from None


@router.get("/notifications")
async def list_notifications(request: Request):
    actor = await require_operator_session(request)
    try:
        return await asyncio.to_thread(notifications(request).list, actor["windows_user"])
    except ValueError as exc:
        raise HTTPException(503, str(exc)) from None


@router.post("/notifications/{identifier}/read")
async def read_notification(identifier: str, request: Request):
    actor = await require_operator_session(request)
    if not await asyncio.to_thread(notifications(request).read, identifier, actor["windows_user"]):
        raise HTTPException(404, "Notificação não encontrada.")
    return {"read": True}


@router.get("/developer/notifications")
async def developer_notifications(request: Request):
    actor = await developer(request)
    try:
        return await asyncio.to_thread(notifications(request).list, actor["windows_user"], developer=True)
    except ValueError as exc:
        raise HTTPException(503, str(exc)) from None


@router.post("/developer/notifications", status_code=201)
async def publish_notification(body: NotificationInput, request: Request):
    actor = await developer(request)
    try:
        return await asyncio.to_thread(notifications(request).publish, body, actor)
    except PermissionError:
        raise HTTPException(403, "Modo desenvolvedor desativado.") from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@router.post("/developer/notifications/{identifier}/archive")
async def archive_notification(identifier: str, request: Request):
    await developer(request)
    try:
        if not await asyncio.to_thread(notifications(request).archive, identifier):
            raise HTTPException(404, "Notificação não encontrada.")
    except PermissionError:
        raise HTTPException(403, "Modo desenvolvedor desativado.") from None
    except ValueError as exc:
        raise HTTPException(503, str(exc)) from None
    return {"archived": True}


@router.get("/schedules")
async def list_schedules(request: Request):
    actor = await require_operator_session(request)
    return await asyncio.to_thread(scheduler(request).list, actor["windows_user"])


@router.post("/schedules", status_code=201)
async def create_schedule(body: ScheduleInput, request: Request):
    actor = await require_operator_session(request)
    return await asyncio.to_thread(scheduler(request).save, body, actor)


@router.put("/schedules/{identifier}")
async def edit_schedule(identifier: str, body: ScheduleInput, request: Request):
    actor = await require_operator_session(request)
    try:
        return await asyncio.to_thread(scheduler(request).save, body, actor, identifier)
    except KeyError:
        raise HTTPException(404, "Agendamento não encontrado neste computador e conta Windows.") from None


@router.delete("/schedules/{identifier}", status_code=204)
async def remove_schedule(identifier: str, request: Request):
    actor = await require_operator_session(request)
    if not await asyncio.to_thread(scheduler(request).repository.remove, identifier, actor["windows_user"]):
        raise HTTPException(404, "Agendamento não encontrado neste computador e conta Windows.")
