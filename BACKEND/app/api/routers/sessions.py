import asyncio

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/hub/session", tags=["operator-session"])


class LoginRequest(BaseModel):
    operator_name: str = Field(min_length=2, max_length=100, pattern=r"^\S(?:.*\S)?$")


def audit(request: Request):
    service = request.app.state.session_audit
    if service is None:
        raise HTTPException(503, "Configure o banco operacional para registrar as sessoes.")
    return service


@router.get("")
async def current(request: Request):
    service = audit(request)
    identifier = request.headers.get("X-Operator-Session")
    session = await asyncio.to_thread(service.session, identifier, touch=True) if identifier else None
    return {"identity": await asyncio.to_thread(service.identity), "session": session,
            "pending_sync": await asyncio.to_thread(service.pending), "sync_error": service.sync_error}


@router.post("")
async def login(body: LoginRequest, request: Request):
    service = audit(request)
    snapshot = (await request.app.state.automation.current()).model_dump(mode="json")
    session = await asyncio.to_thread(service.login, body.operator_name, snapshot)
    return {"identity": await asyncio.to_thread(service.identity), "session": session,
            "pending_sync": await asyncio.to_thread(service.pending), "sync_error": service.sync_error}


@router.delete("", status_code=204)
async def logout(request: Request):
    identifier = request.headers.get("X-Operator-Session")
    if identifier:
        await asyncio.to_thread(audit(request).logout, identifier)
