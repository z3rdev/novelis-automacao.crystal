import asyncio
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.api.operator_session import require_operator_session
from app.domain.chat import (
    ChatError,
    ChatMessageInput,
    ChatReadInput,
    ConversationInput,
    GnreRequestInput,
)
from app.infrastructure.chamados_postgres import CommunicationUnavailable
from app.services.chat_files import MAX_UPLOAD

router = APIRouter(prefix="/hub/chat", tags=["internal-messages"])
OperatorActor = Annotated[dict, Depends(require_operator_session)]


def service(request):
    remote = getattr(request.app.state, "chat_remote", None)
    if remote and remote.profile():
        return remote
    return request.app.state.chat


async def call(function, *args):
    try:
        return await asyncio.to_thread(function, *args)
    except ChatError as exc:
        raise HTTPException(exc.status_code, str(exc)) from None
    except CommunicationUnavailable as exc:
        raise HTTPException(503, str(exc)) from None
    except OSError:
        raise HTTPException(503, "A pasta compartilhada de documentos está indisponível.") from None


@router.get("")
async def inbox(request: Request, actor: OperatorActor):
    return await call(service(request).inbox, actor)


@router.get("/directory")
async def directory(request: Request, actor: OperatorActor):
    return await call(service(request).directory, actor)


@router.post("/rooms", status_code=201)
async def create_room(body: ConversationInput, request: Request, actor: OperatorActor):
    return await call(service(request).create_room, actor, body)


@router.get("/rooms/{room}")
async def room_detail(
    room: UUID,
    request: Request,
    actor: OperatorActor,
    before: int | None = Query(None, ge=1),
):
    return await call(service(request).detail, actor, room, before)


@router.post("/rooms/{room}/messages", status_code=201)
async def send_message(
    room: UUID,
    body: ChatMessageInput,
    request: Request,
    actor: OperatorActor,
):
    message = await call(service(request).send, actor, room, body)
    if realtime := getattr(request.app.state, "chat_realtime", None):
        realtime.changed(room, message)
    return message


@router.post("/rooms/{room}/read", status_code=204)
async def mark_read(
    room: UUID,
    body: ChatReadInput,
    request: Request,
    actor: OperatorActor,
):
    await call(service(request).read, actor, room, body.through)


@router.post("/rooms/{room}/requests", status_code=201)
async def create_request(
    room: UUID,
    body: GnreRequestInput,
    request: Request,
    actor: OperatorActor,
):
    return await call(service(request).request, actor, room, body)


@router.post("/rooms/{room}/requests/{identifier}/claim", status_code=204)
async def claim_request(room: UUID, identifier: UUID, request: Request, actor: OperatorActor):
    await call(service(request).claim, actor, room, identifier)


@router.put("/rooms/{room}/requests/{identifier}/files/{kind}")
async def upload_document(
    room: UUID,
    identifier: UUID,
    kind: Literal["guia", "comprovante"],
    request: Request,
    client_id: UUID,
    actor: OperatorActor,
    filename: str = Query(min_length=1, max_length=240),
):
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_UPLOAD:
            raise HTTPException(413, "Envie um arquivo com até 20 MB.")
        data.extend(chunk)
    return await call(
        service(request).upload, actor, room, identifier, kind, client_id, filename, bytes(data)
    )


@router.get("/rooms/{room}/requests/{identifier}/files/{kind}")
async def download_document(
    room: UUID,
    identifier: UUID,
    kind: Literal["guia", "comprovante", "combined"],
    request: Request,
    actor: OperatorActor,
):
    data, filename = await call(service(request).download, actor, room, identifier, kind)
    return Response(
        data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
