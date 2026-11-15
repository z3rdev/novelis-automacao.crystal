"""The remote protocol accepts a bounded, read-only diagnostic request only."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DiagnosticOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_runs: int = Field(default=10, ge=1, le=20)
    days_back: int = Field(default=7, ge=1, le=30)


class DiagnosticRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_id: UUID
    options: DiagnosticOptions = Field(default_factory=DiagnosticOptions)
