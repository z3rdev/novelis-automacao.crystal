import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ChatError(Exception):
    status_code = 422


class ChatNotFound(ChatError):
    status_code = 404


class ChatConflict(ChatError):
    status_code = 409


class ChatStorageError(ChatError):
    status_code = 503


def cte_code(value: str) -> str:
    if not re.fullmatch(r"\d{1,4}-\d{1,3}-\d{1,10}", value.strip()):
        raise ValueError("Informe filial, série e número do CT-e, como 10-10-2789.")
    return "-".join(str(int(part)) for part in value.strip().split("-"))


class ConversationInput(BaseModel):
    target_type: Literal["operator", "sector"]
    target: str = Field(min_length=1, max_length=160)


class ChatMessageInput(BaseModel):
    client_id: UUID
    body: str = Field(min_length=1, max_length=8000)

    @field_validator("body", mode="before")
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value


class GnreRequestInput(BaseModel):
    cte: str
    note: str = Field(default="", max_length=2000)
    chamado: str = Field(default="", max_length=30, pattern=r"^\d*$")

    @field_validator("cte")
    @classmethod
    def normalize_cte(cls, value):
        return cte_code(value)


class ChatReadInput(BaseModel):
    through: int = Field(ge=0)
