import asyncio
import sqlite3

from fastapi import HTTPException, Request
from app.api.operator_session import require_operator_session

from app.config.settings import Settings
from app.config.env_catalog import EnvCatalog
from app.config.legacy_config import LegacyConfig
from app.domain.run_state import RunState
from app.infrastructure.event_bus import EventBus
from app.services.automation_service import AutomationService
from app.services.browser_driver import BrowserDriver
from app.services.mapping_repository import MappingRepository
from app.services.step_repository import StepRepository


async def require_master_access(request: Request) -> dict:
    from app.services.master_access import MasterDenied
    actor = await require_operator_session(request)
    service = getattr(request.app.state, "master_access", None)
    if not service or not service.store.ready:
        raise HTTPException(503, "O banco compartilhado da senha mestre está indisponível.")
    try:
        await asyncio.to_thread(service.require, actor)
    except MasterDenied as exc:
        raise HTTPException(403, str(exc)) from None
    except (OSError, RuntimeError, sqlite3.Error):
        raise HTTPException(503, "O banco compartilhado da senha mestre está indisponível.") from None
    return actor


def get_settings_from_app(request: Request) -> Settings:
    return request.app.state.settings


def get_env_catalog(request: Request) -> EnvCatalog:
    return request.app.state.env_catalog


def get_legacy_config(request: Request) -> LegacyConfig:
    return request.app.state.legacy_config


def get_repository(request: Request) -> StepRepository:
    return request.app.state.step_repository


def get_mapping_repository(request: Request) -> MappingRepository:
    return request.app.state.mapping_repository


def get_event_bus(request: Request) -> EventBus:
    return request.app.state.event_bus


def get_run_state(request: Request) -> RunState:
    return request.app.state.run_state


def get_automation(request: Request) -> AutomationService:
    return request.app.state.automation


def get_preview_browser(request: Request) -> BrowserDriver:
    return request.app.state.preview_browser.preview_driver()
