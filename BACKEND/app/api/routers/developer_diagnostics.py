import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.routers.operator_features import developer
from app.domain.remote_diagnostics import DiagnosticRequest
from app.infrastructure.chamados_postgres import CommunicationUnavailable
from app.infrastructure.diagnostic_queue import DiagnosticTargetUnavailable

router = APIRouter(
    prefix="/hub/developer/diagnostics",
    tags=["developer-diagnostics"],
    dependencies=[Depends(developer)],
)


async def call(request, method, *args):
    try:
        return await asyncio.to_thread(getattr(request.app.state.diagnostic_queue, method), *args)
    except DiagnosticTargetUnavailable:
        raise HTTPException(
            409, "O computador está offline ou precisa atualizar o agente de diagnóstico."
        ) from None
    except CommunicationUnavailable:
        raise HTTPException(
            503, "Central de diagnóstico indisponível. Verifique o banco de comunicação."
        ) from None


@router.get("/agents")
async def agents(request: Request):
    return {"agents": await call(request, "agents")}


@router.get("")
async def requests(request: Request):
    return {"requests": await call(request, "list")}


@router.post("", status_code=202)
async def create(
    body: DiagnosticRequest, request: Request, actor: Annotated[dict, Depends(developer)]
):
    return await call(
        request, "create", str(body.device_id), actor["windows_user"], body.options.model_dump()
    )


@router.get("/{identifier}")
async def detail(identifier: UUID, request: Request):
    value = await call(request, "get", str(identifier))
    if value is None:
        raise HTTPException(404, "Diagnóstico não encontrado.")
    return value
