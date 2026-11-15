import asyncio
import sqlite3
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, SecretStr

from app.api.deps import require_operator_session
from app.services.master_access import MasterDenied
from app.services.releases.config import DeveloperConfig

router = APIRouter(prefix="/hub/master-access", tags=["master-access"])


class PasswordInput(BaseModel):
    password: SecretStr


def service(request):
    value = getattr(request.app.state, "master_access", None)
    if not value or not value.store.ready:
        raise HTTPException(503, "O banco compartilhado da senha mestre está indisponível.")
    return value


def can_setup(request):
    return DeveloperConfig(request.app.state.settings.backend_root).enabled()


async def invoke(action, *args, **kwargs):
    try:
        return await asyncio.to_thread(action, *args, **kwargs)
    except MasterDenied as exc:
        raise HTTPException(403, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except (OSError, RuntimeError, sqlite3.Error):
        raise HTTPException(503, "O banco compartilhado da senha mestre está indisponível.") from None


async def developer_actor(request):
    actor = await require_operator_session(request)
    if not can_setup(request):
        raise HTTPException(403, "Modo desenvolvedor desativado.")
    return actor


@router.get("/admin")
async def policy(request: Request):
    await developer_actor(request)
    return await invoke(service(request).policy_state)


@router.put("/admin")
async def save_policy(body: PasswordInput, request: Request):
    actor = await developer_actor(request)
    return await invoke(service(request).save_policy, body.password.get_secret_value(), actor, can_manage=True)


@router.get("")
async def status(request: Request):
    actor = await require_operator_session(request)
    return await invoke(service(request).status, actor, can_setup=can_setup(request))


@router.post("/setup")
async def setup(body: PasswordInput, request: Request):
    actor = await require_operator_session(request)
    return await invoke(service(request).setup, body.password.get_secret_value(), actor,
                        can_setup=can_setup(request))


@router.post("/unlock")
async def unlock(body: PasswordInput, request: Request):
    actor = await require_operator_session(request)
    return await invoke(service(request).unlock, body.password.get_secret_value(), actor)


@router.delete("", status_code=204)
async def lock(request: Request):
    actor = await require_operator_session(request)
    service(request).lock(actor)
