import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.automation.flows.sefaz_xml.overlay import fazenda_overlay as overlay


@pytest.fixture
def waiting(monkeypatch):
    values = SimpleNamespace(
        page=object(), control=AsyncMock(return_value={}), update=AsyncMock(),
        marked=AsyncMock(side_effect=[False, False, True]), click=AsyncMock(return_value=True),
    )
    monkeypatch.setattr(overlay, "read_overlay_control", values.control)
    monkeypatch.setattr(overlay, "update_fazenda_overlay", values.update)
    monkeypatch.setattr(overlay, "is_captcha_marked", values.marked)
    monkeypatch.setattr(overlay, "click_captcha_checkbox", values.click)
    return values


def test_wait_clicks_once_and_requires_captcha_confirmation(waiting):
    result = asyncio.run(overlay.wait_for_captcha_marked(waiting.page, {}, poll_ms=1))
    assert result == "checked"
    waiting.click.assert_awaited_once_with(waiting.page)
    assert waiting.marked.await_count == 3


@pytest.mark.parametrize("click_error", [None, RuntimeError("fixture click failure")])
def test_failed_click_keeps_waiting_for_operator(waiting, click_error):
    waiting.marked.side_effect = [False, True]
    waiting.click.return_value = False
    waiting.click.side_effect = click_error
    assert asyncio.run(overlay.wait_for_captcha_marked(waiting.page, {}, poll_ms=1)) == "checked"
    waiting.click.assert_awaited_once()


def test_already_marked_captcha_is_preserved(waiting):
    waiting.marked.side_effect = [True]
    assert asyncio.run(overlay.wait_for_captcha_marked(waiting.page, {})) == "checked"
    waiting.click.assert_not_awaited()


def test_pause_is_respected_before_automatic_click(waiting):
    waiting.control.side_effect = [{"paused": True}, {}, {}]
    waiting.marked.side_effect = [False, True]
    assert asyncio.run(overlay.wait_for_captcha_marked(waiting.page, {}, poll_ms=1)) == "checked"
    waiting.click.assert_awaited_once()
    assert waiting.control.await_count == 3


@pytest.mark.parametrize("action", ["continue", "skip", "stop"])
def test_manual_controls_are_respected_before_click(waiting, action):
    waiting.control.return_value = {"action": action}
    if action == "continue":
        assert asyncio.run(overlay.wait_for_captcha_marked(waiting.page, {})) == "manual_continue"
    else:
        with pytest.raises(overlay.FazendaOverlayAction) as error:
            asyncio.run(overlay.wait_for_captcha_marked(waiting.page, {}))
        assert error.value.action == action
    waiting.click.assert_not_awaited()


def test_timeout_remains_an_error_when_captcha_is_unresolved(waiting):
    waiting.marked.side_effect = None
    waiting.marked.return_value = False
    waiting.click.return_value = False
    with pytest.raises(RuntimeError, match="dentro do tempo"):
        asyncio.run(overlay.wait_for_captcha_marked(waiting.page, {}, timeout_ms=30, poll_ms=1))
    assert waiting.click.await_count > 0


def test_automatic_attempts_finish_while_manual_wait_continues(waiting, monkeypatch):
    waiting.click.return_value = False
    clock = Mock(side_effect=[0, 0.1, 6, 6.1, 6.2])
    monkeypatch.setattr(overlay, "time", SimpleNamespace(monotonic=clock))
    assert asyncio.run(overlay.wait_for_captcha_marked(waiting.page, {}, poll_ms=1)) == "checked"
    waiting.click.assert_awaited_once()
    assert waiting.marked.await_count == 3


def checkbox_page(url, *, marked=False, click_error=None):
    checkbox = SimpleNamespace(
        count=AsyncMock(return_value=1), is_visible=AsyncMock(return_value=True),
        get_attribute=AsyncMock(return_value="true" if marked else "false"),
        click=AsyncMock(side_effect=click_error),
    )
    frame = SimpleNamespace(url=url, locator=lambda _: SimpleNamespace(first=checkbox))
    return SimpleNamespace(frames=[frame]), checkbox


@pytest.mark.parametrize("url", [
    "https://newassets.hcaptcha.com/captcha/v1/test/hcaptcha.html#frame=checkbox",
    "https://www.google.com/recaptcha/api2/anchor?k=test",
    "https://www.recaptcha.net/recaptcha/enterprise/anchor?k=test",
])
def test_click_targets_the_captcha_widget(url):
    page, checkbox = checkbox_page(url)
    assert asyncio.run(overlay.click_captcha_checkbox(page)) is True
    checkbox.click.assert_awaited_once_with(timeout=1_000)


@pytest.mark.parametrize("url", [
    "https://www.cte.fazenda.gov.br/portal/consulta.aspx",
    "https://hcaptcha.com.unrelated.example/checkbox",
    "https://www.google.com/recaptcha/api2/bframe?k=test",
    "https://newassets.hcaptcha.com/captcha/v1/test/hcaptcha.html#frame=challenge",
])
def test_unrelated_checkboxes_and_challenge_frames_are_preserved(url):
    page, checkbox = checkbox_page(url)
    assert asyncio.run(overlay.click_captcha_checkbox(page)) is False
    checkbox.click.assert_not_awaited()


def test_checked_checkbox_is_preserved_during_a_race():
    page, checkbox = checkbox_page("https://newassets.hcaptcha.com/widget", marked=True)
    assert asyncio.run(overlay.click_captcha_checkbox(page)) is False
    checkbox.click.assert_not_awaited()


def test_click_failure_is_recoverable():
    page, checkbox = checkbox_page(
        "https://newassets.hcaptcha.com/widget", click_error=RuntimeError("fixture failure"))
    assert asyncio.run(overlay.click_captcha_checkbox(page)) is False
    checkbox.click.assert_awaited_once()
