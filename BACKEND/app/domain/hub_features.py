from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class NotificationInput(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    body: str = Field(min_length=1, max_length=10000)
    severity: Literal["info", "warning", "critical"] = "info"
    expires_at: datetime | None = None

    @field_validator("title", "body", mode="before")
    @classmethod
    def trim_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("expires_at")
    @classmethod
    def require_timezone(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("Informe o fuso horário da expiração.")
        return value.astimezone(UTC) if value else None


class ScheduleInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    time: str = Field(default="08:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    weekdays: list[int] = Field(default_factory=lambda: list(range(7)), min_length=1, max_length=7)
    flow: Literal["consulta", "somente_pdf", "completo"] = "consulta"
    days_back: int = Field(default=0, ge=0, le=89)
    enabled: bool = True

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("weekdays")
    @classmethod
    def validate_weekdays(cls, value):
        if any(day < 0 or day > 6 for day in value):
            raise ValueError("Dias da semana devem estar entre 0 e 6.")
        return sorted(set(value))
