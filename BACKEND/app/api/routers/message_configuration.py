from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel, Field
from app.api.deps import require_operator_session
from app.api.routers.hub import HubDep
from app.services import message_configuration as messages

router = APIRouter(prefix="/hub/messages", tags=["message-configuration"], dependencies=[Depends(require_operator_session)])


class MessageConfiguration(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    signature: str = Field(max_length=1000)
    message: str = Field(min_length=1, max_length=10000)
    complement_message: str = Field(min_length=1, max_length=10000)
    allow_missing_receipt: bool = False


@router.get("")
def read(hub: HubDep):
    return messages.read(hub.config, hub.store)


@router.put("")
def save(body: MessageConfiguration, request: Request, hub: HubDep):
    from fastapi import HTTPException
    try:
        messages.save(hub.config, hub.store, body.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return messages.read(hub.config)
