import re
import time
from typing import Any

from playwright.async_api import Page


DUPLICATE_CHAMADO_PATTERN = re.compile(r"j[aá] est[aá] cadastrado no chamado", re.IGNORECASE)

SALVAR_CHAMADO_SELECTOR = ", ".join(
    [
        "#salvar",
        'button[name="salvar"]',
        'input[name="salvar"]',
        'button[value="Salvar"]',
        'input[value="Salvar"]',
        'button:has-text("Salvar")',
        '.md-btn:has-text("Salvar")',
    ]
)


async def click_salvar_chamado(page: Page) -> None:
    errors = []
    await dismiss_alertify_if_present(page, total_wait_ms=800, max_clicks=2)
    await _prepare_save_dom(page)
    buttons = page.locator(SALVAR_CHAMADO_SELECTOR)
    count = await _count(buttons)
    if count < 1:
        raise RuntimeError("Botão Salvar não encontrado no DOM.")

    for index in range(count - 1, -1, -1):
        button = buttons.nth(index)
        if not await _button_enabled_visible(button):
            continue
        try:
            before_url = page.url
            await button.scroll_into_view_if_needed(timeout=3_000)
            await button.click(force=True, timeout=7_000)
            if await _wait_click_signal(page, before_url, 3_000):
                return
            errors.append(f"botão[{index}]: sem dialog/toast/navegação")
        except Exception as exc:
            errors.append(f"botão[{index}]: {str(exc).splitlines()[0]}")

    if await _submit_direct(page):
        return
    raise RuntimeError(f"Não foi possível clicar em Salvar. erros={'; '.join(errors[-5:])}")


async def wait_save_confirmation(page: Page, timeout_ms: int = 20_000) -> dict[str, Any]:
    ok_clicks = await dismiss_alertify_if_present(page, total_wait_ms=12_000, max_clicks=4)
    started = time.monotonic()
    while time.monotonic() - started < timeout_ms / 1000:
        toast = page.locator(".ajs-message.ajs-visible").last
        if await _locator_visible(toast, 500):
            text = _normalize(await _safe_text(toast))
            class_name = str(await _safe_attr(toast, "class"))
            if DUPLICATE_CHAMADO_PATTERN.search(text):
                return {
                    "ok": False,
                    "duplicate": True,
                    "message": text or "CTE já cadastrado em outro chamado.",
                    "numero": extract_chamado_numero(text),
                    "okClicks": ok_clicks,
                }
            numero = extract_chamado_numero(text) or await resolve_chamado_numero_from_page(page)
            return {
                "ok": bool(re.search(r"\bajs-success\b", class_name, re.I)) or bool(numero and "erro" not in text.lower()),
                "message": text or "Retorno do Novelis sem texto.",
                "numero": numero,
                "okClicks": ok_clicks,
            }
        numero = await resolve_chamado_numero_from_page(page)
        if numero:
            return {"ok": True, "message": f"Chamado {numero} identificado na página.", "numero": numero}
        await page.wait_for_timeout(500)
    return {
        "ok": False,
        "message": "Salvar foi acionado, mas o Novelis não confirmou criação do chamado.",
        "numero": "",
        "okClicks": ok_clicks,
    }


async def dismiss_alertify_if_present(page: Page, total_wait_ms: int = 4_000, max_clicks: int = 2) -> int:
    started = time.monotonic()
    clicks = 0
    while clicks < max_clicks and time.monotonic() - started < total_wait_ms / 1000:
        ok_button = page.locator(".ajs-modal:visible .ajs-button.ajs-ok, .ajs-dialog:visible .ajs-button.ajs-ok").last
        if await _locator_visible(ok_button, 700):
            await ok_button.click(force=True)
            clicks += 1
            await page.wait_for_timeout(500)
            continue
        await page.wait_for_timeout(180)
    return clicks


async def resolve_chamado_numero_from_page(page: Page) -> str:
    selectors = ["#chamado_h2", "#numero-mobile", "#titulo-chamado", ".titulo-chamado", ".h1_chamado"]
    for selector in selectors:
        text = await _safe_inner_text(page.locator(selector).first)
        numero = extract_chamado_numero(text)
        if numero:
            return numero
    url_match = re.search(r"/portal/chamado/(\d{4,})", page.url, re.I)
    return url_match.group(1) if url_match else ""


def extract_chamado_numero(text: Any) -> str:
    normalized = _normalize(text)
    patterns = [
        r"chamado\s+de\s+n[úu]mero\s+(\d{6,})",
        r"chamado\s+n[úu]mero\s+(\d{6,})",
        r"chamado\s+#?\s*(\d{6,})",
        r"n[úu]mero\s+(\d{6,})",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized, re.I)
        if match:
            return match.group(1)
    return ""


async def _prepare_save_dom(page: Page) -> None:
    await page.evaluate(
        """() => {
            try {
              if (window.tinymce) {
                for (const editor of Array.from(window.tinymce.editors || [])) editor.save?.();
                window.tinymce.activeEditor?.save?.();
              }
            } catch (_) {}
            const buttonFlag = document.querySelector("#button, input[name='button']");
            if (buttonFlag) {
              buttonFlag.value = "salvar";
              buttonFlag.dispatchEvent(new Event("input", { bubbles: true }));
              buttonFlag.dispatchEvent(new Event("change", { bubbles: true }));
            }
            window.scrollTo(0, document.body.scrollHeight);
        }"""
    )
    await page.wait_for_timeout(300)


async def _wait_click_signal(page: Page, previous_url: str, timeout_ms: int) -> str:
    started = time.monotonic()
    while time.monotonic() - started < timeout_ms / 1000:
        if await _count(page.locator(".ajs-dialog:visible")) > 0:
            return "alertify_dialog"
        if await _count(page.locator(".ajs-message.ajs-visible")) > 0:
            return "alertify_toast"
        if previous_url and page.url != previous_url:
            return "url_changed"
        await page.wait_for_timeout(250)
    return ""


async def _submit_direct(page: Page) -> bool:
    result = await page.evaluate(
        """() => {
            const salvar = document.querySelector("#dados_chamado #salvar, #salvar, button[name='salvar']");
            const form = document.querySelector("#dados_chamado form#form") || salvar?.closest?.("form") || document.querySelector("form");
            if (!form) return false;
            form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
            if (typeof form.submit === "function") form.submit();
            return true;
        }"""
    )
    return bool(result)


async def _button_enabled_visible(locator: Any) -> bool:
    try:
        return bool(
            await locator.evaluate(
                """(element) => {
                    const rect = element.getBoundingClientRect();
                    const style = window.getComputedStyle(element);
                    return !element.disabled && element.getAttribute("aria-disabled") !== "true" &&
                      rect.width > 0 && rect.height > 0 && style.display !== "none" && style.visibility !== "hidden";
                }"""
            )
        )
    except Exception:
        return False


async def _count(locator: Any) -> int:
    try:
        return int(await locator.count())
    except Exception:
        return 0


async def _locator_visible(locator: Any, timeout: int = 500) -> bool:
    try:
        return await locator.is_visible(timeout=timeout)
    except Exception:
        return False


async def _safe_text(locator: Any) -> str:
    try:
        return await locator.text_content(timeout=1_000) or ""
    except Exception:
        return ""


async def _safe_inner_text(locator: Any) -> str:
    try:
        return await locator.inner_text(timeout=1_000) or ""
    except Exception:
        return ""


async def _safe_attr(locator: Any, name: str) -> str:
    try:
        return await locator.get_attribute(name, timeout=1_000) or ""
    except Exception:
        return ""


def _normalize(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()
