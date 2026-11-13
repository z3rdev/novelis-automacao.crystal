import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_preview_browser, get_settings_from_app
from app.api.routers.browser import router
from app.automation.flows.legacy_coordinator.controles.coordinator import LegacyCoordinator
from app.config.settings import Settings
from app.domain.models import RunStartRequest
from app.services.flow_catalog import list_flows
from app.services.rodopar_policy import LEGACY_RODOPAR_FLOWS, rodopar_url_blocked


@pytest.mark.parametrize("name", sorted(LEGACY_RODOPAR_FLOWS))
def test_all_legacy_entries_are_blocked_before_browser_access(name):
    config = SimpleNamespace(bool=lambda key, default=False: False)
    coordinator = LegacyCoordinator(None, config, None, None)
    with pytest.raises(RuntimeError, match="Rodopar desabilitado"):
        asyncio.run(coordinator.run(RunStartRequest(flow=name, dry_run=False), "test", object()))


def test_catalog_keeps_disabled_legacy_flow():
    legacy = next(flow for flow in list_flows() if flow.key == "pdf-rodopar")
    assert legacy.enabled is False
    assert next(flow for flow in list_flows(True) if flow.key == "pdf-rodopar").enabled is True


def test_proxy_and_open_api_cannot_start_rodopar():
    settings = Settings(_env_file=None, rodopar_browser_enabled=False)
    browser = SimpleNamespace(open_url=AsyncMock(side_effect=AssertionError("Browser nao pode abrir")))
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_settings_from_app] = lambda: settings
    app.dependency_overrides[get_preview_browser] = lambda: browser
    client = TestClient(app)
    assert client.post("/browser/open", json={}).status_code == 409
    assert client.get("/browser/site/software/html5.html").status_code == 410
    browser.open_url.assert_not_awaited()


def test_only_rodopar_hosts_are_blocked():
    settings = Settings(_env_file=None, rodopar_browser_enabled=False)
    assert rodopar_url_blocked(settings, "https://webcloud16.datapardc.com/software/html5.html")
    assert not rodopar_url_blocked(settings, "https://novelis.wtmh.com.br/login")
    assert not rodopar_url_blocked(settings, "https://www.cte.fazenda.gov.br/")
