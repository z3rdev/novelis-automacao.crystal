from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


StepAction = Literal["click", "fill", "wait", "screenshot", "shortcut", "ocr_click"]
RunStatus = Literal["idle", "running", "stopping", "completed", "failed", "cancelled"]
EventLevel = Literal["debug", "info", "warn", "error"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Viewport(BaseModel):
    width: int = 1024
    height: int = 750
    dpr: float = 1


class StepTemplate(BaseModel):
    path: str = ""
    width: int = 160
    height: int = 70


class StepDefinition(BaseModel):
    number: int = Field(ge=1)
    label: str
    action: StepAction = "click"
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    viewport: Viewport = Field(default_factory=Viewport)
    template: StepTemplate | None = None
    shortcut: str | None = None
    ocr_text: str | None = None
    scroll_x: int | None = None
    scroll_y: int | None = None
    scroll_up_x: int | None = None
    scroll_up_y: int | None = None
    input_key: str | None = None
    enabled: bool = True
    delay_ms: int | None = None
    loop_point: bool = False
    reliable_click: bool | None = None
    requires_manual: bool = False


class StepPatch(BaseModel):
    label: str | None = None
    action: StepAction | None = None
    x: int | None = Field(default=None, ge=0)
    y: int | None = Field(default=None, ge=0)
    shortcut: str | None = None
    ocr_text: str | None = None
    input_key: str | None = None
    enabled: bool | None = None
    delay_ms: int | None = Field(default=None, ge=0)
    loop_point: bool | None = None


class StepCatalog(BaseModel):
    source: str = "pre-passo"
    generated_at: datetime = Field(default_factory=utc_now)
    steps: list[StepDefinition]


MapPointKind = Literal["field", "button", "tab", "region", "other"]
MapFunctionAction = Literal["click", "fill", "wait", "other"]


class RodoparMapTab(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    order: int = 0
    updated_at: datetime = Field(default_factory=utc_now)


class RodoparMapSubTab(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    tab: str = Field(min_length=1)
    description: str = ""
    order: int = 0
    updated_at: datetime = Field(default_factory=utc_now)


class RodoparMapPoint(BaseModel):
    id: str = Field(min_length=1)
    tab: str = Field(min_length=1)
    sub_tab: str = ""
    kind: MapPointKind = "field"
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    x2: int | None = Field(default=None, ge=0)
    y2: int | None = Field(default=None, ge=0)
    viewport: Viewport = Field(default_factory=Viewport)
    description: str = ""
    updated_at: datetime = Field(default_factory=utc_now)


class RodoparFunctionGroup(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    tab: str = Field(min_length=1)
    sub_tab: str = ""
    description: str = ""
    order: int = 0
    updated_at: datetime = Field(default_factory=utc_now)


class RodoparMapFunction(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    tab: str = Field(min_length=1)
    sub_tab: str = ""
    group_id: str = ""
    action: MapFunctionAction = "click"
    point_id: str = ""
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    viewport: Viewport = Field(default_factory=Viewport)
    description: str = ""
    updated_at: datetime = Field(default_factory=utc_now)


class RodoparMapCatalog(BaseModel):
    source: str = "rodopar-preview"
    updated_at: datetime = Field(default_factory=utc_now)
    tabs: list[RodoparMapTab] = Field(default_factory=list)
    sub_tabs: list[RodoparMapSubTab] = Field(default_factory=list)
    points: list[RodoparMapPoint] = Field(default_factory=list)
    function_groups: list[RodoparFunctionGroup] = Field(default_factory=list)
    functions: list[RodoparMapFunction] = Field(default_factory=list)


class ManualSpreadsheetInput(BaseModel):
    filename: str
    content_base64: str


class RunStartRequest(BaseModel):
    flow: str = "pendentes"
    dry_run: bool = True
    execution_scope: Literal["full", "documents", "pdf", "xml"] = "full"
    max_steps: int | None = Field(default=None, ge=1)
    sample_filial: str = ""
    sample_serie: str = ""
    sample_documento: str = ""
    sample_cte: str = ""
    rodopar_replay_overlay_enabled: bool | None = None
    manual_ctes: str = ""
    manual_spreadsheet: ManualSpreadsheetInput | None = None
    pendentes_sql_days_back: int | None = Field(default=None, ge=1, le=90)
    pendentes_skip_chamado_missing_comprovante: bool = True


class ManualConfirmationRequest(BaseModel):
    key: str = "rodopar-login"


class FlowDefinition(BaseModel):
    key: str
    name: str
    description: str
    requires_browser: bool = True
    enabled: bool = True


class RunSnapshot(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    status: RunStatus = "idle"
    flow: str = "pendentes"
    dry_run: bool = True
    current_step: int | None = None
    message: str = "Aguardando execução."
    started_at: datetime | None = None
    finished_at: datetime | None = None


class AutomationEvent(BaseModel):
    id: int
    run_id: str | None = None
    level: EventLevel = "info"
    kind: str = "event"
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class BrowserOpenRequest(BaseModel):
    url: str | None = None


class BrowserClickRequest(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)


class BrowserTypeRequest(BaseModel):
    text: str
