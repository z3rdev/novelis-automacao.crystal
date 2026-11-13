import asyncio
import logging
from contextlib import suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config.env_catalog import EnvCatalog
from app.config.legacy_config import LegacyConfig
from app.config.settings import get_settings
from app.domain.run_state import RunState
from app.infrastructure.event_bus import EventBus
from app.infrastructure.operations_store import OperationsStore
from app.services.automation_service import AutomationService
from app.services.browser_driver import BrowserDriver
from app.services.crystal_reports.service import CrystalReportService
from app.services.dacte_xml import XmlDacteService
from app.services.hub_service import HubService
from app.services.mapping_repository import MappingRepository
from app.services.session_audit import SessionAudit
from app.services.step_repository import StepRepository

logger = logging.getLogger(__name__)


def install_loop_exception_filter() -> None:
    loop = asyncio.get_running_loop()
    previous_handler = loop.get_exception_handler()

    def handle_loop_exception(loop: asyncio.AbstractEventLoop, context: dict) -> None:
        exception = context.get("exception")
        if isinstance(exception, ConnectionResetError) and getattr(exception, "winerror", None) == 10054:
            logger.debug("Conexão cancelada pelo cliente remoto ignorada no preview.")
            return
        if previous_handler:
            previous_handler(loop, context)
        else:
            loop.default_exception_handler(context)

    loop.set_exception_handler(handle_loop_exception)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    step_repository = StepRepository(settings.steps_file)
    mapping_repository = MappingRepository(settings.mapping_file)
    store = OperationsStore(settings.novelis_sqlite_path) if settings.novelis_sqlite_path else None
    audit = SessionAudit(settings.storage_dir / "login-audit.sqlite",
        settings.login_audit_db_path or store.path.parent / "logs/sessoes.sqlite") if store else None
    event_bus = EventBus(store=store)
    run_state = RunState(store=store, audit=audit)

    app.state.settings = settings
    app.state.env_catalog = EnvCatalog(settings)
    app.state.legacy_config = LegacyConfig(settings)
    app.state.crystal_reports = CrystalReportService(settings, app.state.legacy_config)
    app.state.dacte_xml = XmlDacteService(settings, app.state.legacy_config)
    app.state.step_repository = step_repository
    app.state.mapping_repository = mapping_repository
    app.state.event_bus = event_bus
    app.state.run_state = run_state
    app.state.operations_store = store
    app.state.session_audit = audit
    preview_browser = BrowserDriver(settings)
    app.state.preview_browser = preview_browser
    app.state.automation = AutomationService(
        settings,
        app.state.legacy_config,
        step_repository,
        event_bus,
        run_state,
        preview_browser,
    )
    app.state.hub = HubService(settings, app.state.legacy_config, store, app.state.automation, event_bus, audit) if store else None

    app.include_router(api_router)

    @app.on_event("startup")
    async def startup_resources() -> None:
        install_loop_exception_filter()
        if store:
            await asyncio.to_thread(store.initialize)
            app.state.legacy_config.values.update(await asyncio.to_thread(store.preferences))
            await asyncio.to_thread(audit.recover)
            await run_state.restore()
            snapshot = (await run_state.get()).model_dump(mode="json")
            if snapshot["status"] != "idle":
                await asyncio.to_thread(audit.record_run, snapshot, None)
            app.state.audit_sync_task = asyncio.create_task(audit.sync_loop())

    @app.on_event("shutdown")
    async def shutdown_resources() -> None:
        if task := getattr(app.state, "audit_sync_task", None):
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        proxy_client = getattr(app.state, "preview_proxy_client", None)
        if proxy_client is not None:
            await proxy_client.aclose()
        if (await run_state.get()).status in {"running", "stopping"}:
            await app.state.automation.stop()
        await preview_browser.close()
        if store:
            await asyncio.to_thread(store.close)

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"service": settings.app_name, "docs": "/docs", "api": "/api/health"}

    return app


app = create_app()
