import re
import time
from typing import Any

from playwright.async_api import Page


SELECT_CHAMADO_ITEM_JS = """({ expectedText }) => {
    const normalize = (value) =>
      String(value || "")
        .normalize("NFD")
        .replace(/[\\u0300-\\u036f]/g, "")
        .replace(/\\s+/g, " ")
        .trim()
        .toLowerCase();
    const wanted = normalize(expectedText);
    const defaultValue = "0;36";
    const rawSelect = document.querySelector("#tipo_chamado_id");
    const currentVisualItem = document.querySelector(".selectize-input .item");
    if (currentVisualItem && normalize(currentVisualItem.textContent) === wanted) {
      return { ok: true, mode: "already_selectize_item" };
    }
    if (rawSelect) {
      const selectize = rawSelect.selectize;
      if (selectize) {
        const currentValue = String(selectize.getValue?.() || "").trim();
        const currentOption = currentValue ? selectize.options?.[currentValue] : null;
        if (currentValue && normalize(currentOption?.text || "") === wanted) {
          return { ok: true, mode: "already_selectize_api" };
        }
        let targetValue = "";
        const options = selectize.options || {};
        for (const value of Object.keys(options)) {
          const optionText = normalize(options[value]?.text || "");
          if (optionText === wanted || optionText.includes(wanted) || wanted.includes(optionText)) {
            targetValue = value;
            break;
          }
        }
        if (!targetValue && options[defaultValue]) targetValue = defaultValue;
        if (targetValue) {
          selectize.setValue(targetValue, false);
          selectize.trigger?.("change", targetValue);
          rawSelect.dispatchEvent(new Event("input", { bubbles: true }));
          rawSelect.dispatchEvent(new Event("change", { bubbles: true }));
          return { ok: true, mode: "selectize_api", value: targetValue };
        }
      }
      const options = Array.from(rawSelect.options || []);
      const targetOption =
        options.find((option) => normalize(option.textContent) === wanted) ||
        options.find((option) => normalize(option.textContent).includes(wanted)) ||
        options.find((option) => wanted.includes(normalize(option.textContent))) ||
        options.find((option) => String(option.value || "").trim() === defaultValue);
      if (targetOption) {
        rawSelect.value = targetOption.value;
        targetOption.selected = true;
        rawSelect.dispatchEvent(new Event("input", { bubbles: true }));
        rawSelect.dispatchEvent(new Event("change", { bubbles: true }));
        return { ok: true, mode: "native_select", value: targetOption.value };
      }
    }
    const uploadInputs = document.querySelectorAll('input[name^="arquivo["]').length;
    if (uploadInputs >= 3) return { ok: true, mode: "uploads_ready_tipo_ja_aplicado", uploadInputs };
    return {
      ok: false,
      hasRawSelect: Boolean(rawSelect),
      hasSelectizeInput: Boolean(document.querySelector("#tipo_chamado_id-selectized")),
      uploadInputs,
    };
}"""


DETECT_PAGE_CTE_JS = """() => {
    const selectors = ["#titulo-chamado", ".titulo-chamado", ".titulo_com_anexo", "h1", "h2", "#titulo"];
    const values = [];
    for (const selector of selectors) {
      for (const el of document.querySelectorAll(selector)) {
        values.push(el.value || el.innerText || el.textContent || "");
      }
    }
    values.push(document.body?.innerText || "");
    return values.join("\\n").slice(0, 8000);
}"""


async def select_chamado_item(page: Page, item_text: str) -> None:
    if not item_text:
        return
    selected_by_dom = await page.evaluate(SELECT_CHAMADO_ITEM_JS, {"expectedText": item_text})
    if isinstance(selected_by_dom, dict) and selected_by_dom.get("ok"):
        return

    for selector in [f'text="{item_text}"', f'option:has-text("{item_text}")', f'li:has-text("{item_text}")']:
        locator = page.locator(selector).first
        if await _locator_visible(locator):
            await locator.click(force=True)
            return
    raise RuntimeError(f"Não foi possível selecionar o tipo de chamado: {item_text}.")


async def detect_page_cte(page: Page) -> str:
    try:
        text = await page.evaluate(DETECT_PAGE_CTE_JS)
    except Exception:
        return ""
    match = re.search(r"\bCTE\b[^0-9]*([0-9]+)\s*[-/]\s*([0-9]+)\s*[-/]\s*([0-9]+)\b", str(text), re.I)
    return "-".join(match.groups()) if match else ""


async def wait_chamado_form_ready(page: Page, timeout_ms: int = 18_000) -> bool:
    started = time.monotonic()
    timeout_seconds = timeout_ms / 1000
    while time.monotonic() - started < timeout_seconds:
        if await is_chamado_form_ready(page):
            return True
        await page.wait_for_timeout(500)
    return False


async def wait_upload_fields_ready(page: Page, timeout_ms: int = 30_000) -> bool:
    started = time.monotonic()
    timeout_seconds = timeout_ms / 1000
    while time.monotonic() - started < timeout_seconds:
        if await has_upload_fields(page):
            return True
        await page.wait_for_timeout(500)
    return False


async def is_chamado_form_ready(page: Page) -> bool:
    try:
        tipo = await page.locator("#tipo_chamado_id-selectized, #tipo_chamado_id").count()
        uploads = await page.locator('input[name^="arquivo["]').count()
        titulo = await page.locator("#titulo").count()
        return bool(tipo or uploads or titulo)
    except Exception:
        return False


async def has_upload_fields(page: Page) -> bool:
    try:
        return (
            await page.locator('input[name="arquivo[0]"]').count() > 0
            and await page.locator('input[name="arquivo[1]"]').count() > 0
            and await page.locator('input[name="arquivo[2]"]').count() > 0
        )
    except Exception:
        return False


async def upload_file_by_field(
    page: Page,
    field_name: str,
    file_path: str,
    label: str,
    attempts: int = 1,
    retry_delay_ms: int = 0,
) -> None:
    last_error: Exception | None = None
    for attempt in range(1, max(1, attempts) + 1):
        try:
            inputs = page.locator(f'input[name="{field_name}"]')
            input_count = await inputs.count()
            if input_count < 1:
                raise RuntimeError(f"Campo de upload {field_name} não encontrado.")
            for index in range(input_count):
                await inputs.nth(index).set_input_files(file_path)
            empty_count = await page.locator(f'input[name="{field_name}"]').evaluate_all(
                "(elements) => elements.filter((element) => !element.files || element.files.length < 1).length"
            )
            if empty_count:
                raise RuntimeError(f"Upload {label} ainda tem {empty_count}/{input_count} campo(s) vazio(s).")
            return
        except Exception as exc:
            last_error = exc
            if attempt >= max(1, attempts):
                break
            if retry_delay_ms > 0:
                await page.wait_for_timeout(retry_delay_ms)
    if last_error:
        raise last_error


async def _locator_visible(locator: Any, timeout: int = 3_000) -> bool:
    try:
        return await locator.is_visible(timeout=timeout)
    except Exception:
        return False
