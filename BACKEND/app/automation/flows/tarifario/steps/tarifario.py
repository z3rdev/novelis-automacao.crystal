from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.async_api import Page

from app.automation.flows.flow_events import Emit, emit_step, emit_warn
from app.data.consulta_reader import format_currency_br, read_consulta_rows
from app.domain.models import RunStartRequest
from app.infrastructure.json_store import write_json
from app.services.browser_driver import BrowserDriver


class TarifarioFlow:
    def __init__(self, cwd: Path, emit: Emit) -> None:
        self.cwd = cwd
        self.emit = emit

    async def run(
        self,
        browser: BrowserDriver | None,
        config: dict[str, Any],
        request: RunStartRequest,
        run_id: str,
    ) -> list[dict[str, Any]]:
        records = await self._load_records(config, request, run_id)
        if not records:
            self._write_output(config, [])
            return []

        self._write_ton_temp(config, records)
        if request.dry_run:
            rows = [self._with_valor_comparativo(row, config) for row in records]
            self._write_output(config, rows)
            await emit_step(self.emit, run_id, "tarifario.dry_run", "Tarifário simulado.")
            return rows

        if browser is None:
            raise RuntimeError("BrowserDriver obrigatório para tarifário real.")

        page = await browser.new_page()
        try:
            await self._login(page, config, run_id)
            processed: list[dict[str, Any]] = []
            for record in records:
                result = await self._search_row(page, record, config, run_id)
                processed.append({**self._with_valor_comparativo(record, config), **result})
            self._write_output(config, processed)
            return processed
        finally:
            if not config.get("tarifarioKeepTabOpen"):
                await page.close()

    async def _load_records(
        self,
        config: dict[str, Any],
        request: RunStartRequest,
        run_id: str,
    ) -> list[dict[str, Any]]:
        consulta = read_consulta_rows(config, self.cwd)
        await emit_step(
            self.emit,
            run_id,
            "tarifario.consulta",
            f"CONSULTA carregada: {consulta.valid_rows} registro(s).",
            {"sourceFile": consulta.source_file, "sheetName": consulta.sheet_name},
        )
        records = consulta.records
        document_filter = request.sample_documento or str(config.get("documentoFilter") or "")
        if document_filter:
            records = [row for row in records if str(row.get("documento") or "") == document_filter]
            return records
        if config.get("onlySelectedDocumento", True):
            index = max(0, int(config.get("documentoRowIndex") or 0))
            return [records[index]] if index < len(records) else []
        return records

    async def _login(self, page: Page, config: dict[str, Any], run_id: str) -> None:
        await emit_step(self.emit, run_id, "tarifario.open", "Abrindo tarifário Novelis.")
        await page.goto(str(config.get("tarifarioUrl") or ""), wait_until="domcontentloaded")
        await self._wait_network_idle(page, 10_000)
        login_visible = await self._is_visible(page, 'input[name="username"], #username, #email')
        if not login_visible:
            return
        await emit_step(self.emit, run_id, "tarifario.login", "Preenchendo login do tarifário.")
        await page.locator('input[name="username"], #username, #email').first.fill(str(config.get("tarifarioUser") or ""))
        await page.locator('input[type="password"], #password').first.fill(str(config.get("tarifarioPass") or ""))
        await page.locator('button[type="submit"], input[type="submit"]').first.click()
        await self._wait_network_idle(page, 15_000)

    async def _search_row(
        self,
        page: Page,
        row: dict[str, Any],
        config: dict[str, Any],
        run_id: str,
    ) -> dict[str, Any]:
        origem = self._format_uf_cidade(row.get("estCol"), row.get("remCidade"))
        destino = self._format_uf_cidade(row.get("estDes"), row.get("desCidade"))
        await emit_step(
            self.emit,
            run_id,
            "tarifario.search",
            f"Pesquisando tarifa CTE {row.get('documento')}: {origem} -> {destino}.",
        )
        if not origem or not destino:
            await emit_warn(self.emit, run_id, "tarifario.missing_route", "Origem/destino ausente.")
            return {"idTarifario": None, "filteredByTar": False}

        await page.goto(str(config.get("tarifarioUrl") or ""), wait_until="domcontentloaded")
        await self._selectize(page, "#origem-selectized", origem)
        await self._selectize(page, "#destino-selectized", destino)
        await page.locator('input[type="submit"][name="ok"], input[name="ok"]').first.click()
        await page.wait_for_timeout(int(config.get("afterSearchWaitMs") or 1200))
        id_tarifario = await self._extract_tarifario_id(page)
        return {"idTarifario": id_tarifario, "filteredByTar": bool(row.get("vlrTar"))}

    async def _selectize(self, page: Page, selector: str, value: str) -> None:
        field = page.locator(selector).first
        await field.wait_for(state="visible", timeout=15_000)
        await field.fill(value)
        await page.keyboard.press("Enter")

    async def _extract_tarifario_id(self, page: Page) -> str | None:
        try:
            text = await page.locator("tbody tr td").first.text_content(timeout=5_000)
        except Exception:
            text = ""
        return str(text or "").strip() or None

    async def _wait_network_idle(self, page: Page, timeout_ms: int) -> None:
        try:
            await page.wait_for_load_state("networkidle", timeout=timeout_ms)
        except Exception:
            return

    async def _is_visible(self, page: Page, selector: str) -> bool:
        try:
            return await page.locator(selector).first.is_visible(timeout=3_000)
        except Exception:
            return False

    def _write_ton_temp(self, config: dict[str, Any], records: list[dict[str, Any]]) -> None:
        rows = [
            {
                "sheetRow": row.get("sheetRow"),
                "documento": row.get("documento"),
                "percurso": row.get("percurso"),
                "id": row.get("id"),
                "ton": row.get("ton"),
                "tonRaw": row.get("tonRaw"),
                "tonOk": row.get("ton") is not None,
            }
            for row in records
        ]
        output = self._resolve(config.get("tonTempFile") or "captures/ton-temp.json")
        write_json(output, {"generatedAt": self._now(), "total": len(rows), "rows": rows})

    def _write_output(self, config: dict[str, Any], rows: list[dict[str, Any]]) -> None:
        output = self._resolve(config.get("tarifarioOutputFile") or "captures/tarifario-resultados.json")
        write_json(output, {"generatedAt": self._now(), "total": len(rows), "rows": rows})

    def _with_valor_comparativo(self, row: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        tolerance = float(config.get("valorCompareTolerance") or 0)
        freval = row.get("freval") or 0
        outros = row.get("outros") or 0
        vlr_tar = row.get("vlrTar") or 0
        vlr_total = row.get("vlrTotal")
        composicao = freval + outros + vlr_tar
        diferenca = None if vlr_total is None else vlr_total - composicao
        row["valorComparativo"] = {
            "canCompare": vlr_total is not None and row.get("vlrTar") is not None,
            "tolerance": tolerance,
            "composicao": composicao,
            "composicaoFormatted": format_currency_br(composicao),
            "vlrTotal": vlr_total,
            "diferenca": diferenca,
            "bateu": abs(diferenca) <= tolerance if diferenca is not None else None,
        }
        return row

    def _resolve(self, value: str) -> Path:
        path = Path(str(value))
        return path if path.is_absolute() else self.cwd / path

    def _format_uf_cidade(self, uf: Any, cidade: Any) -> str:
        uf_text = str(uf or "").strip()
        cidade_text = str(cidade or "").strip()
        return f"{uf_text} - {cidade_text}" if uf_text else cidade_text

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
