from pathlib import Path
from typing import Any

from playwright.async_api import Page

from app.automation.flows.flow_events import Emit, emit_step, emit_warn
from app.infrastructure.json_store import read_json, write_json
from app.services.browser_driver import BrowserDriver


class GnreFlow:
    def __init__(self, cwd: Path, emit: Emit) -> None:
        self.cwd = cwd
        self.emit = emit

    async def run(
        self,
        browser: BrowserDriver | None,
        config: dict[str, Any],
        row_data: dict[str, Any] | None,
        result_file: str,
        run_id: str,
        dry_run: bool,
    ) -> str | None:
        row = row_data or self.read_tarifario_row(result_file)
        nmgre = str(row.get("nmgre") if row else "").strip()
        if not nmgre:
            await emit_warn(self.emit, run_id, "gnre.skipped", "NMGRE vazio. GNRE pulada.")
            return None
        if dry_run:
            await emit_step(self.emit, run_id, "gnre.dry_run", f"GNRE simulada para NMGRE {nmgre}.")
            return None
        if browser is None:
            raise RuntimeError("BrowserDriver obrigatório para GNRE real.")

        page = await browser.new_page()
        try:
            file_path = await self._run_browser(page, config, row, run_id)
            if file_path:
                self.save_gnre_file_to_result(file_path, result_file, row)
            return file_path
        finally:
            await page.close()

    async def _run_browser(
        self,
        page: Page,
        config: dict[str, Any],
        row: dict[str, Any],
        run_id: str,
    ) -> str | None:
        document_key = self._document_key(row)
        await emit_step(self.emit, run_id, "gnre.open", f"Buscando GNRE {document_key}.")
        await page.goto(str(config.get("url") or ""), wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        await self._ensure_login(page, config, run_id)

        date_cte = str(row.get("dataBR") or "").strip()
        if not date_cte:
            await emit_warn(self.emit, run_id, "gnre.no_date", "Data do CTE ausente.")
            return None

        await self._set_date(page, "#initialDate", date_cte)
        await self._set_date(page, "#endDate", date_cte)
        await page.locator('button:has-text("Filtrar")').click(force=True)
        await page.wait_for_timeout(2500)

        rows = page.locator("table tbody tr")
        count = await rows.count()
        for index in range(count):
            row_locator = rows.nth(index)
            cells = row_locator.locator("td")
            if await cells.count() < 4:
                continue
            doc_text = " ".join(str(await cells.nth(3).text_content() or "").split())
            if doc_text != document_key:
                continue
            return await self._capture_file(page, row_locator, document_key, config, run_id)
        await emit_warn(self.emit, run_id, "gnre.not_found", f"GNRE não localizada: {document_key}.")
        return None

    async def _ensure_login(self, page: Page, config: dict[str, Any], run_id: str) -> None:
        user = page.locator("#loginuser").first
        if not await self._visible(user, timeout=8_000):
            return
        await emit_step(self.emit, run_id, "gnre.login", "Preenchendo login GNRE.")
        await user.fill(str(config.get("user") or ""))
        await page.locator("#loginpassword").fill(str(config.get("pass") or ""))
        await page.locator('button[type="submit"], button:has-text("Entrar")').first.click()
        await page.wait_for_timeout(2500)

    async def _capture_file(
        self,
        page: Page,
        row_locator,
        document_key: str,
        config: dict[str, Any],
        run_id: str,
    ) -> str | None:
        button = row_locator.locator('button[uib-tooltip="Visualizar"]')
        if not await self._visible(button):
            return None
        await button.click(force=True)
        await page.wait_for_selector(".modal-content", timeout=12_000)
        output_dir = self._resolve(config.get("outputDir") or "captures/gnre")
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / f"gnre-{document_key}.png"
        await page.screenshot(path=str(file_path), full_page=False)
        await emit_step(self.emit, run_id, "gnre.saved", f"Evidencia GNRE salva em {file_path}.")
        return str(file_path)

    async def _set_date(self, page: Page, selector: str, value: str) -> None:
        field = page.locator(selector).first
        await field.wait_for(state="visible", timeout=15_000)
        await field.fill("")
        await field.type(value)

    async def _visible(self, locator, timeout: int = 3_000) -> bool:
        try:
            return await locator.is_visible(timeout=timeout)
        except Exception:
            return False

    def read_tarifario_row(self, result_file: str) -> dict[str, Any] | None:
        path = self._resolve(result_file)
        payload = read_json(path, {})
        rows = payload.get("rows") if isinstance(payload, dict) else None
        return rows[0] if isinstance(rows, list) and rows else None

    def save_gnre_file_to_result(
        self,
        gnre_path: str,
        result_file: str,
        row_ref: dict[str, Any] | None,
    ) -> None:
        path = self._resolve(result_file)
        payload = read_json(path, {})
        rows = payload.get("rows") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            return
        target = self._find_row_index(rows, row_ref)
        if target < 0:
            return
        try:
            rel_path = Path(gnre_path).relative_to(self.cwd)
        except ValueError:
            rel_path = Path(gnre_path)
        rows[target]["gnreFile"] = str(rel_path).replace("\\", "/")
        write_json(path, payload)

    def _find_row_index(self, rows: list[dict[str, Any]], row_ref: dict[str, Any] | None) -> int:
        if not row_ref:
            return 0 if rows else -1
        doc = self._digits(row_ref.get("documento"))
        serie = self._digits(row_ref.get("serie"))
        for index, row in enumerate(rows):
            if self._digits(row.get("documento")) == doc and self._digits(row.get("serie")) == serie:
                return index
        return -1

    def _document_key(self, row: dict[str, Any]) -> str:
        return f"{self._digits(row.get('documento'))}-{self._digits(row.get('serie'))}"

    def _digits(self, value: Any) -> str:
        return "".join(ch for ch in str(value or "") if ch.isdigit())

    def _resolve(self, value: str) -> Path:
        path = Path(str(value))
        return path if path.is_absolute() else self.cwd / path
