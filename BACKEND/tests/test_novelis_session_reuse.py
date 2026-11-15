import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import urlsplit

import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeout

from app.automation.flows.novelis_chamados.controles.portal_session import open_authenticated

ORIGIN = "https://novelis.wtmh.com.br"
CONFIG = {"user": "session-fixture", "pass": "session-fixture-secret"}


class Locator:
    def __init__(self, page, selector):
        self.page, self.selector = page, selector
        self.first = self

    async def is_visible(self):
        return urlsplit(self.page.url).path == "/login" and "password" in self.selector

    async def fill(self, value):
        self.page.fills.append(self.selector)

    async def click(self):
        self.page.logins += 1
        if self.page.accept_login:
            self.page.authenticated = True
            self.page.url = ORIGIN + "/portal/dashboard"


class Page:
    def __init__(self, authenticated=False, accept_login=True):
        self.url = "about:blank"
        self.authenticated, self.accept_login = authenticated, accept_login
        self.gets, self.fills, self.logins = [], [], 0

    async def goto(self, url, **kwargs):
        self.gets.append(url)
        self.url = url if self.authenticated else ORIGIN + "/login"
        return SimpleNamespace(status=200)

    def locator(self, selector):
        return Locator(self, selector)

    async def wait_for_url(self, predicate, **kwargs):
        if not predicate(self.url):
            raise PlaywrightTimeout("fixture-login-refused")


def test_many_new_chamados_share_one_browser_session_and_login_once():
    async def exercise():
        page, emit = Page(), AsyncMock()
        for index in range(5):
            await open_authenticated(
                page, ORIGIN + f"/portal/chamado/?fixture={index}", CONFIG, emit, "run"
            )
        assert page.logins == 1 and len(page.fills) == 2
        assert len(page.gets) == 6  # Five protected GETs, one repeat after initial login.
        kinds = [call.kwargs.get("kind") for call in emit.await_args_list]
        assert kinds.count("novelis.login") == 1 and kinds.count("novelis.session_reused") == 4
        page.authenticated = False
        await open_authenticated(
            page, ORIGIN + "/portal/chamado/?fixture=expired", CONFIG, emit, "run"
        )
        assert page.logins == 2

    asyncio.run(exercise())


def test_existing_authenticated_context_never_opens_login_or_sends_credentials():
    page = Page(authenticated=True)
    asyncio.run(open_authenticated(page, ORIGIN + "/portal/chamado/", CONFIG, AsyncMock(), "run"))
    assert page.gets == [ORIGIN + "/portal/chamado/"]
    assert page.logins == 0 and page.fills == []


def test_failed_authentication_is_not_repeated_and_cannot_be_mistaken_for_ready_form():
    page = Page(accept_login=False)
    with pytest.raises(RuntimeError, match="não confirmado"):
        asyncio.run(
            open_authenticated(page, ORIGIN + "/portal/chamado/", CONFIG, AsyncMock(), "run")
        )
    assert page.logins == 1 and len(page.gets) == 1


def test_missing_credentials_and_wrong_target_do_not_submit_any_login():
    page = Page()
    with pytest.raises(RuntimeError, match="Configure a conta"):
        asyncio.run(open_authenticated(page, ORIGIN + "/portal/chamado/", {}, AsyncMock(), "run"))
    with pytest.raises(RuntimeError, match="oficial"):
        asyncio.run(
            open_authenticated(page, "https://invalid.example/collect", CONFIG, AsyncMock(), "run")
        )
    assert page.logins == 0 and page.fills == []


def test_permission_denied_does_not_trigger_blind_login_attempts():
    page = Page(authenticated=True)
    original = page.goto

    async def forbidden(*args, **kwargs):
        await original(*args, **kwargs)
        return SimpleNamespace(status=403)

    page.goto = forbidden
    with pytest.raises(RuntimeError, match="recusou acesso"):
        asyncio.run(
            open_authenticated(page, ORIGIN + "/portal/chamado/", CONFIG, AsyncMock(), "run")
        )
    assert page.logins == 0
