from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import FileResponse
from playwright.async_api import Error as PlaywrightError
from pydantic import BaseModel, Field, model_validator
from datetime import date
from app.domain.consultation_period import validate_period

from app.api.routers.health import _read_app_version
from app.services.hub_service import HubService
from app.api.deps import require_master_access, require_operator_session
from app.infrastructure.chamados_postgres import CommunicationUnavailable

router = APIRouter(prefix="/hub", tags=["cargo-hub"])


def get_hub(request: Request):
    hub = request.app.state.hub
    if not hub or not hub.store.ready:
        raise HTTPException(503, "Banco operacional nao configurado. Configure NOVELIS_SQLITE_PATH no backend local.")
    return hub


HubDep = Annotated[HubService, Depends(get_hub)]


class StartRequest(BaseModel):
    flow: Literal["completo", "documentos", "somente_pdf", "somente_xml", "somente_comprovantes", "buscar_chamados", "somente_chamados", "consulta"] = "completo"
    ctes: list[str] = Field(default_factory=list, max_length=500)
    periodoDias: int = Field(default=5, ge=0, le=90)
    dataInicio: date | None = None
    dataFim: date | None = None
    chamadoHttp: bool = False

    @model_validator(mode="after")
    def period(self):
        validate_period(self.dataInicio, self.dataFim)
        return self

    def range_options(self):
        return {"date_start": self.dataInicio, "date_end": self.dataFim} if self.dataInicio else {}


@router.get("/health/ping")
def ping(hub: HubDep):
    return {"versao": _read_app_version(hub.settings.backend_root.parent)}


@router.get("/overview")
async def overview(hub: HubDep):
    try:
        return await hub.overview()
    except OSError:
        raise HTTPException(503, "Verificacao dos arquivos indisponivel. Verifique acesso as pastas configuradas.") from None
    except CommunicationUnavailable:
        raise HTTPException(503, "Não foi possível conferir os chamados já abertos no banco de comunicação.") from None


@router.get("/ctes")
def ctes(hub: HubDep):
    try:
        return hub.ctes()
    except OSError:
        raise HTTPException(503, "Verificacao dos arquivos indisponivel. Verifique acesso as pastas configuradas.") from None
    except CommunicationUnavailable:
        raise HTTPException(503, "Não foi possível conferir os chamados já abertos no banco de comunicação.") from None


@router.post("/ctes/refresh")
async def refresh(body: StartRequest, request: Request, hub: HubDep):
    try:
        await hub.start("consulta", [], body.periodoDias, request.headers.get("X-Operator-Session"), **body.range_options())
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"atualizados": 0, "state": "executando"}


@router.get("/runs/current")
async def current(hub: HubDep):
    return await hub.run()


@router.post("/runs")
async def start(body: StartRequest, request: Request, hub: HubDep):
    try:
        return await hub.start(body.flow, body.ctes, body.periodoDias, request.headers.get("X-Operator-Session"), http_test=body.chamadoHttp, **body.range_options())
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/runs/current/stop")
async def stop(hub: HubDep):
    await hub.automation.stop()
    return await hub.run()


@router.get("/documents/dacte/jobs")
def jobs(hub: HubDep):
    return hub.jobs()


class GenerateRequest(BaseModel):
    ctes: list[str] = Field(min_length=1, max_length=500)
    metodo: Literal["crystal", "xml"] = "crystal"


@router.post("/documents/dacte/generate", status_code=202)
async def generate(body: GenerateRequest, request: Request, hub: HubDep):
    if body.metodo != "crystal":
        raise HTTPException(422, "Lote XML ainda nao integrado nesta tela; a rota individual XML permanece disponivel.")
    try:
        await hub.start("somente_pdf", body.ctes, 5, request.headers.get("X-Operator-Session"))
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"accepted": True}


@router.get("/documents/dacte/file/{identifier}")
def document(identifier: str, hub: HubDep):
    job = next((value for value in hub.jobs() if value["id"] == identifier), {})
    path = Path(job.get("arquivo", ""))
    if job.get("state") != "concluida" or not path.is_file():
        raise HTTPException(404, "PDF nao encontrado.")
    return FileResponse(path, media_type="application/pdf")


@router.get("/chamados")
def chamados(hub: HubDep):
    return hub.chamados()


@router.get("/chamados/page")
def chamados_page(hub: HubDep, search: str = Query(default="", max_length=200),
                  status: Literal["todos", "na_fila", "aberto", "em_analise", "solucionado", "falhou"] = "todos",
                  page: int = Query(default=0, ge=0), size: int = Query(default=100, ge=1, le=100)):
    from app.infrastructure.chamados_postgres import CommunicationUnavailable
    try:
        return hub.chamados_catalog.page(search=search, status=status, page=page, size=size)
    except CommunicationUnavailable as exc:
        raise HTTPException(503, str(exc)) from None


@router.get("/chamados/summary")
def chamados_summary(hub: HubDep):
    repository = hub.chamados_catalog.repository
    if not repository.enabled:
        raise HTTPException(503, "Configure o PostgreSQL de comunicação para consultar os chamados centralizados.")
    try:
        # Menu polling only reads aggregates. Source imports stay in the background worker.
        return {"counts": repository.counts()}
    except CommunicationUnavailable:
        raise HTTPException(503, "Contagem dos chamados indisponível. Verifique o banco de comunicação.") from None


@router.get("/chamados/{identifier}", dependencies=[Depends(require_operator_session)])
def chamado_detail(identifier: str, hub: HubDep):
    from app.infrastructure.chamados_postgres import CommunicationUnavailable
    try:
        value = hub.chamados_catalog.detail(identifier)
    except CommunicationUnavailable as exc:
        raise HTTPException(503, str(exc)) from None
    if not value:
        raise HTTPException(404, "Chamado não encontrado no catálogo de comunicação.")
    return value


@router.get("/logs")
def logs(hub: HubDep, since: str | None = None):
    if since and not since.isdecimal():
        raise HTTPException(422, "Cursor de eventos invalido.")
    return hub.logs(since)


@router.get("/health/diagnostics", dependencies=[Depends(require_master_access)])
def health(hub: HubDep):
    return hub.database_health()


@router.get("/config", dependencies=[Depends(require_master_access)])
def configuration(hub: HubDep):
    return hub.config_groups()


@router.put("/config", dependencies=[Depends(require_master_access)])
def save_configuration(body: list[dict], hub: HubDep):
    try:
        hub.save_config(body)
    except (ValueError, KeyError) as exc:
        raise HTTPException(422, "Configuracao invalida.") from exc
    return {"saved": True}


@router.get("/automation/browser")
async def browser(request: Request, hub: HubDep):
    driver = request.app.state.preview_browser
    if hasattr(driver, "preview_driver"):
        driver = driver.preview_driver()
    state = driver.state()
    result = {"url": next(iter(state.get("urls", [])), ""), "titulo": "Navegador da automacao",
              "acao": "Nenhum navegador aberto nesta etapa.", "ativo": bool(state.get("open"))}
    if result["ativo"]:
        try:
            snapshot = await driver.snapshot()
            result.update(url=snapshot["url"], screenshot=snapshot["image"], acao="Captura do navegador neste computador")
        except (PlaywrightError, OSError, RuntimeError):
            result["acao"] = "Navegador aberto; captura temporariamente indisponivel."
    return result


@router.post("/automation/browser/focus")
async def focus_browser(request: Request, hub: HubDep):
    driver = request.app.state.preview_browser.preview_driver()
    if not driver.state().get("open"):
        raise HTTPException(409, "Nenhum navegador aberto nesta etapa.")
    await driver.focus_page(driver.page)
    return {"focused": True}


@router.get("/automation/steps")
def steps(request: Request, hub: HubDep):
    values = request.app.state.step_repository.list().steps
    return [{"id": str(s.number), "ordem": s.number, "nome": s.label, "acao": s.action,
             "seletor": "", "aba": "", "timeoutMs": s.delay_ms or 0,
             "captura": s.action == "screenshot", "ativo": s.enabled} for s in values]


@router.put("/automation/steps")
def save_steps(body: list[dict], request: Request, hub: HubDep):
    raise HTTPException(409, "Edicao de passos nesta tela ainda nao integrada. Use o editor existente de pontos e passos.")
