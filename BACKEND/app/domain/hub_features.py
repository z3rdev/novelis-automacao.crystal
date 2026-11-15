from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.scheduled_workflow import ScheduledWorkflow


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
    flow: Literal[
        "consulta",
        "somente_pdf",
        "somente_xml",
        "somente_comprovantes",
        "buscar_chamados",
        "completo",
        "personalizado",
    ] = "consulta"
    workflow: ScheduledWorkflow | None = None
    days_back: int = Field(default=0, ge=0, le=30)
    enabled: bool = True
    runs_per_day: int = Field(default=1, ge=1, le=48)
    interval_minutes: int = Field(default=60, ge=1, le=1440)
    max_retries: int = Field(default=0, ge=0, le=10)
    retry_interval_minutes: int = Field(default=5, ge=1, le=1440)

    @model_validator(mode="after")
    def check_workflow(self):
        hour, minute = map(int, self.time.split(":"))
        if hour * 60 + minute + (self.runs_per_day - 1) * self.interval_minutes >= 1440:
            raise ValueError(
                "As execuções do dia devem terminar de ser iniciadas antes da meia-noite."
            )
        if self.flow == "personalizado" and self.workflow is None:
            raise ValueError("Crie o fluxo do agendamento.")
        return self

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
