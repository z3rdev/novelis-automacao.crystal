import asyncio
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.api.deps import require_operator_session
from app.infrastructure.chamados_postgres import CommunicationUnavailable

router = APIRouter(
    prefix="/hub/tariffs", tags=["tariffs"], dependencies=[Depends(require_operator_session)]
)


def service(request: Request):
    return request.app.state.tariffs


def unavailable():
    return HTTPException(
        503, "Catálogo de tarifas indisponível. Verifique o banco de comunicação e a sincronização."
    )


@router.get("")
async def page(
    request: Request,
    search: str = Query("", max_length=160),
    origin: str = Query("", max_length=12),
    destination: str = Query("", max_length=12),
    vehicle: str = Query("", max_length=100),
    validity: Literal["todos", "vigente", "vencida", "futura", "inconsistente"] = "vigente",
    page: int = Query(0, ge=0),
    size: int = Query(50, ge=1, le=100),
):
    try:
        return await asyncio.to_thread(
            service(request).page,
            search=search,
            origin=origin,
            destination=destination,
            vehicle=vehicle,
            validity=validity,
            page=page,
            size=size,
        )
    except CommunicationUnavailable:
        raise unavailable() from None


@router.get("/cities")
async def cities(request: Request, search: str = Query("", max_length=120)):
    try:
        return await asyncio.to_thread(service(request).cities, search)
    except CommunicationUnavailable:
        raise unavailable() from None


@router.get("/sync")
async def sync_status(request: Request):
    try:
        return await asyncio.to_thread(service(request).status)
    except CommunicationUnavailable:
        raise unavailable() from None


@router.post("/sync", status_code=202)
async def sync(request: Request):
    try:
        return await service(request).refresh(force=True)
    except CommunicationUnavailable:
        raise unavailable() from None


class Calculation(BaseModel):
    tonnes: str = Field(min_length=1, max_length=30)


@router.post("/{identifier}/estimate")
async def calculate(identifier: str, body: Calculation, request: Request):
    try:
        return await asyncio.to_thread(service(request).calculate, identifier, body.tonnes)
    except CommunicationUnavailable:
        raise unavailable() from None
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
