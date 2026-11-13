import asyncio
import time
from contextlib import suppress
from typing import Any
from urllib.parse import urlsplit

from playwright.async_api import Locator, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError


class FazendaValidationError(RuntimeError):
    pass


class FazendaOverlayAction(RuntimeError):
    def __init__(self, action: str) -> None:
        super().__init__(f"Acao do overlay: {action}")
        self.action = action


async def update_fazenda_overlay(page: Page, state: dict[str, Any]) -> None:
    if page.is_closed():
        return
    payload = {
        "title": "CTE Fazenda",
        "cte": "",
        "cteId": "",
        "phase": "",
        "message": "",
        "primaryLabel": "Continuar",
        "showPrimary": True,
        **state,
    }
    await page.evaluate(
        """(payload) => {
          const rootId = "cte-fazenda-overlay";
          let root = document.getElementById(rootId);
          if (!window.__cteFazendaOverlay) {
            window.__cteFazendaOverlay = { action: "", paused: false };
          }
          if (!root) {
            root = document.createElement("div");
            root.id = rootId;
            root.innerHTML = `
              <style>
                #${rootId} {
                  position: fixed; top: 12px; right: 12px; z-index: 2147483647;
                  width: 330px; font-family: Arial, Helvetica, sans-serif;
                  color: #15201d; pointer-events: none;
                }
                #${rootId} .panel {
                  pointer-events: auto; background: rgba(255,255,255,.97);
                  border: 1px solid #bec8c3; border-radius: 8px;
                  box-shadow: 0 16px 42px rgba(0,0,0,.22); overflow: hidden;
                }
                #${rootId} .head {
                  display: flex; justify-content: space-between; gap: 8px;
                  padding: 9px 10px; background: #102f27; color: #fff;
                  font: 700 13px Arial, Helvetica, sans-serif;
                }
                #${rootId} .body {
                  padding: 10px; display: grid; gap: 8px;
                  font: 12px/1.35 Arial, Helvetica, sans-serif;
                }
                #${rootId} .line {
                  display: flex; justify-content: space-between; gap: 10px;
                }
                #${rootId} .label { color: #5a6862; font-weight: 700; }
                #${rootId} .value {
                  color: #10201b; font-weight: 700; text-align: right;
                  overflow-wrap: anywhere;
                }
                #${rootId} .message {
                  min-height: 34px; padding: 8px; border: 1px solid #d7dedb;
                  border-radius: 6px; background: #f6f8f7; color: #26332f;
                  overflow-wrap: anywhere;
                }
                #${rootId} .actions { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
                #${rootId} button {
                  min-height: 31px; border: 1px solid #b8c3be; border-radius: 6px;
                  background: #fff; color: #17342d; font-weight: 700;
                  font-size: 12px; cursor: pointer;
                }
                #${rootId} button.primary { background: #0d6efd; border-color: #0d6efd; color: #fff; }
                #${rootId} button.danger { background: #c82333; border-color: #c82333; color: #fff; }
              </style>
              <div class="panel">
                <div class="head">
                  <span data-role="title"></span>
                  <span data-role="phase"></span>
                </div>
                <div class="body">
                  <div class="line"><span class="label">CTE</span><span class="value" data-role="cte"></span></div>
                  <div class="line"><span class="label">Chave</span><span class="value" data-role="cteId"></span></div>
                  <div class="message" data-role="message"></div>
                  <div class="actions">
                    <button class="primary" data-role="primary"></button>
                    <button data-role="pause"></button>
                    <button data-action="skip">Pular</button>
                    <button class="danger" data-action="stop">Parar</button>
                  </div>
                </div>
              </div>`;
            document.documentElement.appendChild(root);
            root.querySelector('[data-role="primary"]').onclick = () => {
              window.__cteFazendaOverlay.action = "continue";
            };
            root.querySelector('[data-role="pause"]').onclick = () => {
              window.__cteFazendaOverlay.paused = !window.__cteFazendaOverlay.paused;
            };
            root.querySelector('[data-action="skip"]').onclick = () => {
              window.__cteFazendaOverlay.action = "skip";
            };
            root.querySelector('[data-action="stop"]').onclick = () => {
              window.__cteFazendaOverlay.action = "stop";
            };
          }
          const setText = (role, value) => {
            const el = root.querySelector(`[data-role="${role}"]`);
            if (el) el.textContent = String(value || "");
          };
          const primary = root.querySelector('[data-role="primary"]');
          const pause = root.querySelector('[data-role="pause"]');
          setText("title", payload.title);
          setText("phase", payload.phase);
          setText("cte", payload.cte);
          setText("cteId", payload.cteId);
          setText("message", payload.message);
          if (primary) {
            primary.textContent = String(payload.primaryLabel || "Continuar");
            primary.style.display = payload.showPrimary === false ? "none" : "";
          }
          if (pause) {
            pause.textContent = window.__cteFazendaOverlay.paused ? "Retomar" : "Pausar";
          }
        }""",
        payload,
    )


async def read_overlay_control(page: Page) -> dict[str, Any]:
    try:
        return await page.evaluate(
            """() => {
              const overlay = window.__cteFazendaOverlay || { action: "", paused: false };
              const action = String(overlay.action || "");
              overlay.action = "";
              return { action, paused: Boolean(overlay.paused) };
            }"""
        )
    except Exception:
        return {"action": "", "paused": False}


async def wait_if_paused(page: Page, state: dict[str, Any], poll_ms: int = 250) -> None:
    while True:
        control = await read_overlay_control(page)
        _throw_for_overlay_action(control.get("action", ""))
        if not control.get("paused"):
            return
        await update_fazenda_overlay(page, {**state, "message": "Automação pausada pelo overlay."})
        await asyncio.sleep(poll_ms / 1000)


async def wait_for_captcha_marked(
    page: Page,
    state: dict[str, Any],
    timeout_ms: int = 180_000,
    poll_ms: int = 250,
) -> str:
    started_at = time.monotonic()
    deadline = started_at + (timeout_ms / 1000)
    automatic_click_deadline = min(deadline, started_at + 5)
    automatic_click_pending = True
    await update_fazenda_overlay(
        page,
        {
            **state,
            "phase": "hCaptcha",
            "message": (
                "Tentando clicar no checkbox do hCaptcha. Se aparecer um desafio, "
                "conclua no navegador para continuar automaticamente."
            ),
            "primaryLabel": "Continuar mesmo assim",
            "showPrimary": True,
        },
    )
    while time.monotonic() < deadline:
        control = await read_overlay_control(page)
        _throw_for_overlay_action(control.get("action", ""))
        if control.get("action") == "continue":
            return "manual_continue"
        if control.get("paused"):
            await asyncio.sleep(poll_ms / 1000)
            continue
        if await is_captcha_marked(page):
            await update_fazenda_overlay(
                page,
                {
                    **state,
                    "phase": "hCaptcha",
                    "message": "hCaptcha marcado. Continuando automaticamente.",
                    "showPrimary": False,
                },
            )
            return "checked"
        if automatic_click_pending:
            clicked = False
            with suppress(Exception):
                clicked = await click_captcha_checkbox(page)
            automatic_click_pending = not clicked and time.monotonic() < automatic_click_deadline
            if not automatic_click_pending:
                message = (
                    "Clique enviado ao hCaptcha. Se aparecer um desafio, conclua no navegador."
                    if clicked else
                    "Tentativa de clique encerrada. Conclua o hCaptcha no navegador para continuar."
                )
                await update_fazenda_overlay(page, {**state, "phase": "hCaptcha", "message": message})
        await asyncio.sleep(poll_ms / 1000)
    raise RuntimeError("Captcha da Sefaz não foi resolvido dentro do tempo.")


async def is_locator_visible(locator: Locator) -> bool:
    try:
        return await locator.is_visible(timeout=1_000)
    except Exception:
        return False


async def click_and_wait_maybe_navigates(
    page: Page,
    locator: Locator,
    timeout_ms: int,
) -> None:
    try:
        async with page.expect_navigation(wait_until="domcontentloaded", timeout=timeout_ms):
            await locator.click(timeout=timeout_ms)
    except PlaywrightTimeoutError:
        pass
    except Exception:
        await locator.click(timeout=timeout_ms)
    with suppress(Exception):
        await page.wait_for_load_state("domcontentloaded", timeout=min(timeout_ms, 30_000))


async def wait_for_visible_or_manual(
    page: Page,
    selector: str,
    label: str,
    timeout_ms: int,
    manual_message: str,
    state: dict[str, Any],
) -> Locator:
    locator = page.locator(selector).first
    deadline = time.monotonic() + (timeout_ms / 1000)
    while time.monotonic() < deadline:
        await throw_if_fazenda_validation_error(page, state)
        if await is_locator_visible(locator):
            return locator
        await asyncio.sleep(0.5)

    await update_fazenda_overlay(
        page,
        {
            **state,
            "phase": label,
            "message": manual_message,
            "primaryLabel": "Continuar",
            "showPrimary": True,
        },
    )
    while True:
        control = await read_overlay_control(page)
        _throw_for_overlay_action(control.get("action", ""))
        if control.get("action") == "continue" and await is_locator_visible(locator):
            return locator
        await asyncio.sleep(0.25)


async def throw_if_fazenda_validation_error(page: Page, state: dict[str, Any]) -> None:
    message = await get_fazenda_validation_message(page)
    if not message:
        return
    await update_fazenda_overlay(
        page,
        {
            **state,
            "phase": "Erro Fazenda",
            "message": f"Fazenda retornou erro: {message}.",
            "showPrimary": False,
        },
    )
    raise FazendaValidationError(message)


async def get_fazenda_validation_message(page: Page) -> str:
    try:
        messages = await page.locator(
            "#ctl00_ContentPlaceHolder1_bltMensagensErroHCaptcha li, "
            "#ctl00_ContentPlaceHolder1_bltMensagensErro li, "
            "ul.listaErro li, .listaErro li"
        ).evaluate_all(
            """items => items.map((item) => String(item.textContent || "").trim()).filter(Boolean)"""
        )
        return " | ".join(messages) if isinstance(messages, list) else ""
    except Exception:
        return ""


async def is_captcha_marked(page: Page) -> bool:
    token_selectors = (
        'textarea[name="h-captcha-response"]',
        'textarea[name="g-recaptcha-response"]',
        'input[name="h-captcha-response"]',
        'input[name="g-recaptcha-response"]',
    )
    for selector in token_selectors:
        if await _locator_has_value(page.locator(selector).first):
            return True
    for frame in page.frames:
        try:
            checkbox = frame.locator("#checkbox[role='checkbox'], #checkbox").first
            if await checkbox.count():
                checked = await checkbox.get_attribute("aria-checked", timeout=300)
                if str(checked or "").lower() == "true":
                    return True
            for selector in token_selectors:
                if await _locator_has_value(frame.locator(selector).first):
                    return True
        except Exception:
            continue
    return False


async def click_captcha_checkbox(page: Page) -> bool:
    for frame in page.frames:
        try:
            url = urlsplit(frame.url)
            host = (url.hostname or "").lower()
            hcaptcha = (
                host == "hcaptcha.com" or host.endswith(".hcaptcha.com")
            ) and "frame=challenge" not in url.fragment
            recaptcha = (
                host in {"google.com", "recaptcha.net"}
                or host.endswith((".google.com", ".recaptcha.net"))
            ) and url.path.endswith("/anchor") and "/recaptcha/" in url.path
            if not (hcaptcha or recaptcha):
                continue
            locator = frame.locator("#checkbox, #recaptcha-anchor").first
            if not await locator.count() or not await is_locator_visible(locator):
                continue
            if await locator.get_attribute("aria-checked", timeout=300) == "true":
                return False
            await locator.click(timeout=1_000)
            return True
        except Exception:
            continue
    return False


async def _locator_has_value(locator: Locator) -> bool:
    try:
        if not await locator.count():
            return False
        value = await locator.input_value(timeout=300)
        return bool(str(value or "").strip())
    except PlaywrightTimeoutError:
        return False
    except Exception:
        return False


def _throw_for_overlay_action(action: str) -> None:
    if action in {"skip", "stop"}:
        raise FazendaOverlayAction(action)
