import asyncio
import logging
import os
import sqlite3
from contextlib import suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.api.routers.health import _read_release_version
from app.config.env_catalog import EnvCatalog
from app.config.legacy_config import LegacyConfig
from app.config.settings import get_settings
from app.domain.run_state import RunState
from app.infrastructure.event_bus import EventBus
from app.infrastructure.notifications import NotificationRepository
from app.infrastructure.operations_store import OperationsStore
from app.infrastructure.schedules import ScheduleRepository
from app.infrastructure.diagnostic_queue import DiagnosticQueue
from app.services.automation_service import AutomationService
from app.services.browser_driver import BrowserDriver
from app.services.crystal_reports.service import CrystalReportService
from app.services.dacte_xml import XmlDacteService
from app.services.desktop_lifecycle import monitor_desktop
from app.services.device_presence import DevicePresence
from app.services.remote_diagnostics.agent import DiagnosticAgent
from app.services.hub_service import HubService
from app.services.mapping_repository import MappingRepository
from app.services.master_access import MasterAccess
from app.services.local_document_retention import LocalDocumentRetention
from app.services.notification_server import NotificationServer
from app.services.notifications import NotificationService
from app.services.releases.config import DeveloperConfig
from app.services.releases.publisher import ReleasePublisher
from app.services.releases.service import ReleaseService
from app.services.scheduler import ScheduleEngine
from app.services.session_audit import SessionAudit
from app.services.chat import ChatService
from app.services.chat_archive import ChatArchive
from app.services.chat_remote import RemoteChat
from app.services.device_identity import device_identity
from app.services.preview_persona import finance_identity, restrict_finance_preview
from app.services.step_repository import StepRepository
from app.services.tariffs.service import TariffService
from app.services.execution_reports.service import ExecutionReports

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
    persona = finance_identity(settings)
    if persona:
        restrict_finance_preview(app)
    app.state.readiness_probe = os.environ.get("NOVELIS_BACKEND_READINESS") == "1"

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    step_repository = StepRepository(settings.steps_file)
    mapping_repository = MappingRepository(settings.mapping_file)
    store = OperationsStore(settings.novelis_sqlite_path,
        machine_id=persona()["computer_name"].casefold() if persona else None) if settings.novelis_sqlite_path else None
    audit = SessionAudit(settings.storage_dir / "login-audit.sqlite",
        settings.login_audit_db_path or store.path.parent / "logs/sessoes.sqlite",
        identity=persona or device_identity) if store else None
    event_bus = EventBus(store=store)
    run_state = RunState(store=store, audit=audit)

    app.state.settings = settings
    app.state.releases = ReleaseService(settings.backend_root.parent, _read_release_version(settings.backend_root.parent))
    app.state.release_publisher = ReleasePublisher(settings.backend_root.parent, app.state.releases.storage)
    app.state.env_catalog = EnvCatalog(settings)
    app.state.legacy_config = LegacyConfig(settings)
    app.state.chat = ChatService(settings, app.state.legacy_config)
    app.state.chat_remote = RemoteChat(settings.backend_root, app.state.legacy_config)
    app.state.chat_archive = ChatArchive(app.state.chat, store)
    app.state.tariffs = TariffService(app.state.legacy_config)
    app.state.crystal_reports = CrystalReportService(settings, app.state.legacy_config)
    app.state.dacte_xml = XmlDacteService(settings, app.state.legacy_config)
    app.state.step_repository = step_repository
    app.state.mapping_repository = mapping_repository
    app.state.event_bus = event_bus
    app.state.run_state = run_state
    app.state.device_presence = DevicePresence(audit, settings.backend_root.parent, run_state) if audit and not app.state.readiness_probe else None
    app.state.diagnostic_queue = DiagnosticQueue(app.state.legacy_config)
    app.state.diagnostic_agent = DiagnosticAgent(settings, app.state.legacy_config, app.state.device_presence,
        app.state.diagnostic_queue) if app.state.device_presence else None
    app.state.operations_store = store
    app.state.master_access = MasterAccess(store) if store else None
    app.state.session_audit = audit
    app.state.execution_reports = ExecutionReports(settings, app.state.legacy_config, store, audit) if store else None
    preview_browser = BrowserDriver(settings)
    app.state.preview_browser = preview_browser
    app.state.automation = AutomationService(
        settings,
        app.state.legacy_config,
        step_repository,
        event_bus,
        run_state,
        preview_browser,
        run_reports=app.state.execution_reports,
    )
    app.state.hub = HubService(settings, app.state.legacy_config, store, app.state.automation, event_bus, audit) if store else None
    app.state.document_retention = LocalDocumentRetention(settings, app.state.legacy_config, app.state.automation)
    app.state.notifications = NotificationService(NotificationRepository(store),
        NotificationServer(DeveloperConfig(settings.backend_root))) if store else None
    app.state.scheduler = ScheduleEngine(ScheduleRepository(store), app.state.hub, audit, event_bus) if store else None

    app.include_router(api_router)

    @app.on_event("startup")
    async def startup_resources() -> None:
        install_loop_exception_filter()
        app.state.desktop_parent_task = None if app.state.readiness_probe else monitor_desktop()
        if store:
            await asyncio.to_thread(store.initialize)
            app.state.legacy_config.values.update(await asyncio.to_thread(store.preferences))
            if app.state.readiness_probe:
                return
            if persona:
                await asyncio.to_thread(audit.recover)
                app.state.audit_sync_task = asyncio.create_task(audit.sync_loop())
                app.state.device_presence.start()
                return
            app.state.tariffs.start()
            app.state.chat_archive.start()
            app.state.execution_reports.start()
            await asyncio.to_thread(audit.recover)
            await app.state.scheduler.recover()
            await run_state.restore()
            snapshot = (await run_state.get()).model_dump(mode="json")
            if snapshot["status"] != "idle":
                await asyncio.to_thread(audit.record_run, snapshot, None)
            app.state.audit_sync_task = asyncio.create_task(audit.sync_loop())
            app.state.notification_sync_task = asyncio.create_task(app.state.notifications.sync_loop())
            app.state.device_presence.start()
            app.state.diagnostic_agent.start()
            app.state.scheduler.start()
            app.state.hub.chamados_catalog.start()
            app.state.document_retention.start()

    @app.on_event("shutdown")
    async def shutdown_resources() -> None:
        await asyncio.to_thread(app.state.chat_remote.close)
        await app.state.chat_archive.close()
        if app.state.diagnostic_agent:
            await app.state.diagnostic_agent.close()
        await app.state.tariffs.close()
        if app.state.execution_reports:
            await app.state.execution_reports.close()
        await app.state.document_retention.close()
        if task := getattr(app.state, "notification_sync_task", None):
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        if task := getattr(app.state, "desktop_parent_task", None):
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        if app.state.scheduler:
            await app.state.scheduler.close()
        if app.state.hub:
            await app.state.hub.chamados_catalog.close()
        await app.state.release_publisher.close()
        await app.state.releases.close()
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
        if app.state.device_presence:
            try:
                await app.state.device_presence.close()
                await asyncio.to_thread(audit.sync)
            except (OSError, RuntimeError, sqlite3.Error):
                logger.warning("O encerramento do aplicativo aguarda sincronização dos registros locais.")
        if store:
            await asyncio.to_thread(store.close)

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"service": settings.app_name, "docs": "/docs", "api": "/api/health"}

    return app


app = create_app()
