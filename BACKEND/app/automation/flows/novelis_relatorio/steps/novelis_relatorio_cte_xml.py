import calendar
import re
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from playwright.async_api import Page

from app.automation.flows.flow_events import Emit, emit_step, emit_warn
from app.automation.flows.novelis_chamados.steps.novelis import NovelisFlow
from app.infrastructure.json_store import read_json, write_json
from app.services.browser_driver import BrowserDriver


class NovelisRelatorioCteXmlFlow:
    def __init__(self, cwd: Path, emit: Emit) -> None:
        self.cwd = cwd
        self.emit = emit

    async def run(
        self,
        browser: BrowserDriver | None,
        config: dict[str, Any],
        source_rows: list[dict[str, Any]],
        run_id: str,
    ) -> dict[str, Any]:
        prepared_rows = [{**row, "sheetRow": row.get("sheetRow") or index + 1} for index, row in enumerate(source_rows)]
        base = self._base_result(prepared_rows)

        if config.get("relatorioCteXmlEnabled") is False:
            return {**base, "skipped": True, "error": "NOVELIS_RELATORIO_CTE_XML_ENABLED=false"}

        cached = self._load_fresh_cache(config) if config.get("relatorioCteXmlSkipIfFreshToday", True) else None
        json_file = self._json_file(config)
        if cached:
            download_info, report_rows, generated_at = cached
            await emit_step(
                self.emit,
                run_id,
                "novelis_relatorio.cache_reused",
                f"Relatório Novelis já atualizado hoje ({generated_at}); reaproveitando sem baixar de novo.",
                {"excelFile": str(download_info["file"]), "jsonFile": str(json_file or "")},
            )
            payload = self._payload(download_info, report_rows)
        else:
            if browser is None:
                return {**base, "skipped": True, "error": "Browser indisponível para baixar Excel Novelis."}

            page = await self._novelis_page(browser)
            await NovelisFlow(self.cwd, self.emit).ensure_portal_authenticated(page, config, run_id)
            download_info = await self._download_excel(page, config, run_id)
            report_rows = self._parse_excel(download_info["file"])
            payload = self._payload(download_info, report_rows)
            if json_file:
                write_json(json_file, payload)

        rows_with_id = [row for row in prepared_rows if self._row_key(row)]
        if not rows_with_id:
            await emit_warn(
                self.emit,
                run_id,
                "novelis_relatorio.no_cte_id",
                "Excel Novelis baixado, mas não há CTE_ID na fila para comparar.",
                {"excelFile": str(download_info["file"]), "jsonFile": str(json_file or "")},
            )
            return {
                **base,
                "checked": 0,
                "excelFile": str(download_info["file"]),
                "jsonFile": str(json_file or ""),
                "dateRange": download_info["dateRange"],
                "payload": payload,
            }

        match_by_key = {row["key"]: row for row in report_rows if row.get("key")}
        match_by_serie_nct = {
            f"{self._part(row.get('serie'))}|{self._part(row.get('nCT') or row.get('documento'))}": row
            for row in report_rows
            if row.get("serie") or row.get("nCT") or row.get("documento")
        }
        kept_rows, existing_rows = self._split_existing(prepared_rows, match_by_key, match_by_serie_nct)
        serie_matches = self._count_serie_nct_matches(prepared_rows, match_by_serie_nct)

        await emit_step(
            self.emit,
            run_id,
            "novelis_relatorio.filtered",
            (
                f"Relatório Novelis: {len(report_rows)} CTE(s) no Excel, "
                f"{len(existing_rows)} já existente(s), {len(kept_rows)} pendente(s)."
            ),
            {
                "excelFile": str(download_info["file"]),
                "jsonFile": str(json_file or ""),
                "matched": len(existing_rows),
                "kept": len(kept_rows),
                "totalSerieNctMatches": serie_matches,
            },
        )
        return {
            **base,
            "rows": kept_rows,
            "existingRows": existing_rows,
            "checked": len(rows_with_id),
            "matched": len(existing_rows),
            "totalSerieNctMatches": serie_matches,
            "excelFile": str(download_info["file"]),
            "jsonFile": str(json_file or ""),
            "dateRange": download_info["dateRange"],
            "payload": payload,
        }

    async def _novelis_page(self, browser: BrowserDriver) -> Page:
        page = await browser.find_page_by_url("novelis")
        if page is None:
            page = await browser.new_page()
        return await browser.focus_page(page)

    async def _download_excel(self, page: Page, config: dict[str, Any], run_id: str) -> dict[str, Any]:
        date_range = self._date_range(config)
        await self._open_relatorio_page(page, config, run_id)
        await self._set_input(page, "#uk_dp_start, input[name='de']", date_range["startBR"])
        await self._set_input(page, "#uk_dp_end, input[name='ate']", date_range["endBR"])

        timeout = max(10_000, int(config.get("relatorioCteXmlDownloadTimeoutMs") or 120_000))
        await emit_step(
            self.emit,
            run_id,
            "novelis_relatorio.download",
            f"Baixando Excel Novelis de {date_range['startBR']} ate {date_range['endBR']}.",
        )
        async with page.expect_download(timeout=timeout) as download_info:
            await page.locator("#excel").first.click(force=True)
        download = await download_info.value
        failure = await download.failure()
        if failure:
            raise RuntimeError(f"Download do relatório XML CTE falhou: {failure}")

        suggested_name = (download.suggested_filename or "relatorio_cte.xlsx").strip()
        output = self._excel_file(config, suggested_name)
        output.parent.mkdir(parents=True, exist_ok=True)
        await download.save_as(str(output))
        await emit_step(
            self.emit,
            run_id,
            "novelis_relatorio.downloaded",
            f"Excel Novelis salvo em {output}.",
            {"excelFile": str(output), "suggestedName": suggested_name},
        )
        return {
            "file": output,
            "suggestedName": suggested_name,
            "sourceUrl": page.url,
            "dateRange": date_range,
        }

    async def _open_relatorio_page(self, page: Page, config: dict[str, Any], run_id: str) -> None:
        relatorio_url = self._custom_url(config)
        dashboard_url = str(config.get("dashboardUrl") or config.get("portalUrl") or "").strip()
        await emit_step(self.emit, run_id, "novelis_relatorio.open", "Abrindo relatório XML CTE.")
        if dashboard_url:
            await page.goto(dashboard_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(600)

        try:
            clicked = await page.evaluate(
                """() => {
                    const links = Array.from(document.querySelectorAll("a[href]"));
                    const link = links.find((item) => String(item.getAttribute("href") || "")
                      .includes("/custom/relatorio_cte_xml"));
                    if (!link) return false;
                    link.click();
                    return true;
                }"""
            )
        except Exception:
            clicked = False
        if clicked:
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=15_000)
            except Exception:
                pass
            await page.wait_for_timeout(800)

        has_filter = await page.locator("#uk_dp_start, input[name='de']").first.count()
        if not has_filter:
            await page.goto(relatorio_url, wait_until="domcontentloaded")

        await page.locator("#uk_dp_start, input[name='de']").first.wait_for(state="attached", timeout=20_000)
        await page.locator("#uk_dp_end, input[name='ate']").first.wait_for(state="attached", timeout=20_000)
        await page.locator("#excel").first.wait_for(state="attached", timeout=20_000)

    async def _set_input(self, page: Page, selector: str, value: str) -> None:
        await page.locator(selector).first.wait_for(state="attached", timeout=10_000)
        await page.evaluate(
            """({ selector, value }) => {
                const input = document.querySelector(selector);
                if (!input) return false;
                input.focus();
                input.value = "";
                input.dispatchEvent(new Event("input", { bubbles: true }));
                input.value = value;
                input.dispatchEvent(new Event("input", { bubbles: true }));
                input.dispatchEvent(new Event("change", { bubbles: true }));
                input.dispatchEvent(new Event("blur", { bubbles: true }));
                return true;
            }""",
            {"selector": selector, "value": value},
        )

    def _parse_excel(self, file_path: Path) -> list[dict[str, Any]]:
        workbook = load_workbook(file_path, data_only=True, read_only=True)
        parsed: list[dict[str, Any]] = []
        for sheet_name in workbook.sheetnames:
            rows = list(workbook[sheet_name].iter_rows(values_only=True))
            header_index, indexes = self._header_indexes(rows)
            if indexes is None:
                continue
            for index, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
                item = self._row_from_report(row, indexes, sheet_name, index)
                if item:
                    parsed.append(item)
        return self._dedupe_report_rows(parsed)

    def _header_indexes(self, rows: list[tuple[Any, ...]]) -> tuple[int, dict[str, int] | None]:
        for index, row in enumerate(rows[:25]):
            headers = [self._header(value) for value in row]
            id_idx = self._find_column(headers, ["ID", "CTE_ID", "CTEID", "ID_CTE"])
            serie_idx = self._find_column(headers, ["SERIE"])
            nct_idx = self._find_column(headers, ["NCT", "N_CT", "NUMERO", "DOCUMENTO", "NROCTE"])
            if id_idx >= 0 and serie_idx >= 0 and nct_idx >= 0:
                return index, {
                    "id": id_idx,
                    "serie": serie_idx,
                    "nct": nct_idx,
                    "chamado": self._find_column(headers, ["NUMERODOCHAMADO", "CHAMADO"]),
                    "andamento": self._find_column(headers, ["ANDAMENTO", "STATUS"]),
                    "responsavel": self._find_column(headers, ["RESPONSAVEL"]),
                    "aberto": self._find_column(headers, ["ABERTOEM", "ABERTO"]),
                }
        return -1, None

    def _row_from_report(
        self,
        row: tuple[Any, ...],
        indexes: dict[str, int],
        sheet_name: str,
        row_number: int,
    ) -> dict[str, Any] | None:
        raw_id = self._text_at(row, indexes["id"])
        serie = self._part(self._text_at(row, indexes["serie"]))
        nct = self._part(self._text_at(row, indexes["nct"]))
        key = self._build_key(raw_id, serie, nct)
        if not key:
            return None
        return {
            "sourceKind": "relatorio_cte_xml",
            "id": raw_id,
            "cteId": raw_id,
            "cteIdDigits": self._digits(raw_id),
            "serie": serie,
            "nCT": nct,
            "documento": nct,
            "key": key,
            "chamadoNumero": self._text_at(row, indexes.get("chamado", -1)).replace(" ", ""),
            "andamento": self._text_at(row, indexes.get("andamento", -1)),
            "atualResponsavel": self._text_at(row, indexes.get("responsavel", -1)),
            "abertoEm": self._text_at(row, indexes.get("aberto", -1)),
            "sourceSheet": sheet_name,
            "sourceRow": row_number,
        }

    def _split_existing(
        self,
        rows: list[dict[str, Any]],
        match_by_key: dict[str, dict[str, Any]],
        match_by_serie_nct: dict[str, dict[str, Any]] | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        kept_rows: list[dict[str, Any]] = []
        existing_rows: list[dict[str, Any]] = []
        for row in rows:
            hit = match_by_key.get(self._row_key(row))
            if not hit and match_by_serie_nct:
                fallback_key = f"{self._part(row.get('serie'))}|{self._part(row.get('documento'))}"
                if fallback_key != "|":
                    hit = match_by_serie_nct.get(fallback_key)
            if not hit:
                kept_rows.append({**row, "__novelis": {"prechecked": True, "alreadyExists": False}})
                continue
            existing_rows.append(
                {
                    **row,
                    "__novelis": {
                        "prechecked": True,
                        "alreadyExists": True,
                        "chamadoNumero": hit.get("chamadoNumero") or "",
                        "andamento": hit.get("andamento") or "",
                        "atualResponsavel": hit.get("atualResponsavel") or "",
                        "abertoEm": hit.get("abertoEm") or "",
                        "relatorioKey": hit.get("key") or "",
                        "excelFile": hit.get("excelFile") or "",
                    },
                }
            )
        return kept_rows, existing_rows

    def _count_serie_nct_matches(
        self,
        rows: list[dict[str, Any]],
        match_by_serie_nct: dict[str, dict[str, Any]],
    ) -> int:
        count = 0
        for row in rows:
            key = f"{self._part(row.get('serie'))}|{self._part(row.get('documento'))}"
            if key != "|" and key in match_by_serie_nct:
                count += 1
        return count

    def _payload(self, download_info: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
        enriched = [{**row, "excelFile": str(download_info["file"])} for row in rows]
        return {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "sourceUrl": download_info["sourceUrl"],
            "excelFile": str(download_info["file"]),
            "suggestedName": download_info["suggestedName"],
            "dateRange": download_info["dateRange"],
            "totalUniqueCte": len(enriched),
            "rows": enriched,
        }

    def _base_result(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "rows": rows,
            "existingRows": [],
            "skipped": False,
            "error": "",
            "checked": 0,
            "matched": 0,
            "totalSerieNctMatches": 0,
            "excelFile": "",
            "jsonFile": "",
            "dateRange": None,
        }

    def _date_range(self, config: dict[str, Any]) -> dict[str, str]:
        today = date.today()
        end_day = calendar.monthrange(today.year, today.month)[1]
        end = date(today.year, today.month, end_day)
        start = self._parse_date_start(config) or date(today.year, 1, 1)
        return {"startBR": start.strftime("%d/%m/%Y"), "endBR": end.strftime("%d/%m/%Y")}

    def _parse_date_start(self, config: dict[str, Any]) -> date | None:
        raw = str(config.get("relatorioCteXmlDateStart") or "").strip()
        if not raw:
            return None
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                continue
        return None

    def _custom_url(self, config: dict[str, Any]) -> str:
        raw = str(config.get("relatorioCteXmlUrl") or "").strip()
        if raw:
            return raw
        base = str(config.get("dashboardUrl") or config.get("portalUrl") or "").strip()
        if base:
            match = re.match(r"^(https?://[^/]+)", base)
            if match:
                return f"{match.group(1)}/custom/relatorio_cte_xml"
        return "https://novelis.wtmh.com.br/custom/relatorio_cte_xml"

    def _excel_file(self, config: dict[str, Any], suggested_name: str) -> Path:
        raw = str(config.get("relatorioCteXmlExcelFile") or "").strip()
        path = self._resolve(raw) if raw else self._resolve(f"captures/novelis-relatorio-cte-xml/{suggested_name}")
        return path

    def _json_file(self, config: dict[str, Any]) -> Path | None:
        raw = str(config.get("relatorioCteXmlJsonFile") or "").strip()
        return self._resolve(raw) if raw else None

    def _load_fresh_cache(
        self,
        config: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict[str, Any]], str] | None:
        json_file = self._json_file(config)
        if not json_file or not json_file.is_file():
            return None
        try:
            payload = read_json(json_file, {})
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        generated_at = str(payload.get("generatedAt") or "")
        if not self._is_today(generated_at):
            return None
        rows = payload.get("rows")
        if not isinstance(rows, list):
            return None
        report_rows = [row for row in rows if isinstance(row, dict)]
        excel_file = str(payload.get("excelFile") or "")
        download_info = {
            "file": Path(excel_file) if excel_file else json_file,
            "suggestedName": Path(excel_file).name if excel_file else json_file.name,
            "sourceUrl": str(payload.get("sourceUrl") or ""),
            "dateRange": payload.get("dateRange"),
        }
        return download_info, report_rows, generated_at

    def _is_today(self, iso_value: str) -> bool:
        if not iso_value:
            return False
        try:
            parsed = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
        except ValueError:
            return False
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).date() == datetime.now(timezone.utc).date()

    def _row_key(self, row: dict[str, Any]) -> str:
        return self._build_key(row.get("cteId") or row.get("CTE_ID"), row.get("serie"), row.get("documento"))

    def _build_key(self, cte_id: Any, serie: Any, nct: Any) -> str:
        id_digits = self._digits(cte_id)
        serie_key = self._part(serie)
        nct_key = self._part(nct)
        return f"{id_digits}|{serie_key}|{nct_key}" if id_digits and serie_key and nct_key else ""

    def _dedupe_report_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in rows:
            key = str(row.get("key") or "")
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(row)
        return out

    def _find_column(self, headers: list[str], candidates: list[str]) -> int:
        normalized = [self._header(candidate) for candidate in candidates]
        for candidate in normalized:
            if candidate in headers:
                return headers.index(candidate)
        return -1

    def _header(self, value: Any) -> str:
        text = unicodedata.normalize("NFD", str(value or ""))
        text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
        return re.sub(r"[^A-Z0-9]+", "", text.upper()).strip()

    def _text_at(self, row: tuple[Any, ...], index: int) -> str:
        if index < 0 or index >= len(row):
            return ""
        return "" if row[index] is None else str(row[index]).strip()

    def _digits(self, value: Any) -> str:
        return re.sub(r"\D+", "", str(value or ""))

    def _part(self, value: Any) -> str:
        digits = self._digits(value)
        return digits.lstrip("0") or digits or str(value or "").strip().upper()

    def _resolve(self, value: str) -> Path:
        path = Path(str(value or ""))
        return path if path.is_absolute() else self.cwd / path
