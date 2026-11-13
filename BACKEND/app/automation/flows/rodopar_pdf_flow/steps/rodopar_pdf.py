import asyncio
import re
import time
from pathlib import Path
from typing import Any

from playwright.async_api import Page

from app.automation.flows.flow_events import Emit, emit_step, emit_warn
from app.automation.flows.pre_passo.steps.pre_passo_legacy import PrePassoLegacyFlow
from app.automation.flows.rodopar_pdf_flow.controles.downloads import RodoparPdfDownloadWatcher
from app.automation.flows.rodopar_pdf_flow.overlay.replay_overlay import RodoparReplayOverlay
from app.automation.steps.pointer_map_steps import find_step_number, load_pointer_map_steps
from app.config.settings import Settings
from app.data.consulta_reader import read_consulta_rows
from app.domain.models import RunStartRequest, StepDefinition
from app.services.browser_driver import BrowserDriver
from app.services.manual_confirmation import (
    DEFAULT_CONFIRMATION_KEY,
    consume_manual_confirmation,
    reset_manual_confirmation,
)
from app.services.step_repository import StepRepository


DEFAULT_FIRST_START_STEP = 1
DEFAULT_LOOP_START_STEP = 5
DEFAULT_LOOP_END_STEP = 18
DEFAULT_MANUAL_LOGIN_TIMEOUT_SEC = 900


class RodoparPdfFlow:
    def __init__(self, settings: Settings, repository: StepRepository, emit: Emit) -> None:
        self.settings = settings
        self.repository = repository
        self.emit = emit

    async def run(
        self,
        browser: BrowserDriver | None,
        config: dict[str, Any],
        request: RunStartRequest,
        run_id: str,
    ) -> list[dict[str, Any]]:
        rows = await self._resolve_rows(config, request, run_id)
        if not rows:
            await emit_warn(
                self.emit,
                run_id,
                "rodopar_pdf.no_rows",
                "Nenhum CTRC encontrado para baixar PDF no Rodopar.",
            )
            return []

        rodopar_steps = self._rodopar_steps(config)
        first_step, loop_start, loop_end = self._step_window(config, rodopar_steps)
        await emit_step(
            self.emit,
            run_id,
            "rodopar_pdf.plan",
            (
                f"Rodopar PDF: {len(rows)} CTRC(s). "
                f"Primeiro {first_step}-{loop_end}; proximos {loop_start}-{loop_end}."
            ),
            {
                "rows": rows,
                "downloadTargetDir": str(config.get("downloadTargetDir") or ""),
                "firstStartStep": first_step,
                "loopStartStep": loop_start,
                "loopEndStep": loop_end,
                "captureFile": str(config.get("captureFile") or ""),
                "stepCount": len(rodopar_steps),
            },
        )

        if request.dry_run:
            return rows
        if browser is None:
            raise RuntimeError("BrowserDriver obrigatório para Rodopar PDF real.")

        pre_flow = PrePassoLegacyFlow(self.settings, self.repository, self.emit)
        page = await self._open_rodopar_page(pre_flow, browser, config, request, run_id)
        await self._wait_for_manual_rodopar_login(page, browser, config, run_id)
        if not rodopar_steps:
            rodopar_steps = await self._configure_empty_map(page, config, run_id)
            first_step, loop_start, loop_end = self._step_window(config, rodopar_steps)
            if not rodopar_steps:
                await emit_warn(
                    self.emit,
                    run_id,
                    "rodopar_pdf.empty_map_cancelled",
                    "Mapa Rodopar PDF continua vazio. Nenhum passo foi executado.",
                )
                return rows
        failed_rows: list[dict[str, Any]] = []
        for index, row in enumerate(rows):
            await emit_step(
                self.emit,
                run_id,
                "rodopar_pdf.progress",
                f"Rodopar PDF {index + 1}/{len(rows)}: CTRC {row['filial']}-{row['serie']}-{row['documento']}.",
                {
                    "current": index + 1,
                    "total": len(rows),
                    "cte": f"{row['filial']}-{row['serie']}-{row['documento']}",
                },
            )
            started_at = time.time()
            watcher = RodoparPdfDownloadWatcher(self.settings, config, row, self.emit, run_id)
            known_files = watcher.known_files()
            watcher.attach(page)
            start_step = first_step if index == 0 else loop_start
            row_request = request.model_copy(
                update={
                    "max_steps": None,
                    "sample_filial": row["filial"],
                    "sample_serie": row["serie"],
                    "sample_documento": row["documento"],
                }
            )
            await emit_step(
                self.emit,
                run_id,
                "rodopar_pdf.row_started",
                (
                    f"Baixando PDF CTRC {row['filial']}-{row['serie']}-{row['documento']} "
                    f"({index + 1}/{len(rows)})."
                ),
                {"row": row, "startStep": start_step, "endStep": loop_end},
            )
            try:
                try:
                    page = await pre_flow.replay_range(
                        page,
                        browser,
                        config,
                        row_request,
                        run_id,
                        start_step,
                        loop_end,
                        steps_override=rodopar_steps,
                        steps_reloader=lambda: self._rodopar_steps(config),
                    )
                    pdf_file = ""
                    if config.get("renameDownloadsToCte") is not False:
                        pdf_file = await watcher.wait_and_rename(known_files, started_at)
                finally:
                    watcher.detach()
            except Exception as exc:
                if config.get("stopOnError"):
                    raise
                await emit_warn(
                    self.emit,
                    run_id,
                    "rodopar_pdf.row_failed",
                    (
                        f"Rodopar PDF falhou para CTRC {row['filial']}-{row['serie']}-{row['documento']} "
                        f"({index + 1}/{len(rows)}): {exc}. Seguindo para o próximo CTRC."
                    ),
                    {"row": row},
                )
                failed_rows.append({**row, "reason": str(exc)})
                continue
            await emit_step(
                self.emit,
                run_id,
                "rodopar_pdf.row_completed",
                f"Rodopar PDF concluído para CTRC {row['filial']}-{row['serie']}-{row['documento']}.",
                {"row": row, "pdfFile": pdf_file},
            )
        if failed_rows:
            await emit_warn(
                self.emit,
                run_id,
                "rodopar_pdf.completed_with_failures",
                (
                    f"Rodopar PDF terminou com {len(failed_rows)} de {len(rows)} CTRC(s) sem PDF. "
                    "Revise o mapa de passos para o(s) CTRC(s) que falharam."
                ),
                {"failedRows": failed_rows},
            )
        return rows

    async def _open_rodopar_page(
        self,
        pre_flow: PrePassoLegacyFlow,
        browser: BrowserDriver,
        config: dict[str, Any],
        request: RunStartRequest,
        run_id: str,
    ) -> Page:
        login_request = request.model_copy(update={"max_steps": None})
        page = await pre_flow.run_initial(
            browser,
            {
                **config,
                "manualLoginOnly": True,
                "manualLogin": False,
                "replayFromCapture": False,
                "replayContinueAfterTarifario": False,
            },
            login_request,
            run_id,
        )
        if page is None:
            raise RuntimeError("Tela HTML5 do Rodopar não foi aberta.")
        return page

    async def _wait_for_manual_rodopar_login(
        self,
        page: Page,
        browser: BrowserDriver,
        config: dict[str, Any],
        run_id: str,
    ) -> None:
        timeout_s = self._positive_int(
            config.get("rodoparManualLoginTimeoutSec"),
            DEFAULT_MANUAL_LOGIN_TIMEOUT_SEC,
        )
        reset_manual_confirmation(self.settings, run_id, DEFAULT_CONFIRMATION_KEY)
        deadline = time.time() + timeout_s
        await browser.focus_page(page)
        await emit_warn(
            self.emit,
            run_id,
            "rodopar_pdf.html5_detected_pause",
            "HTML5 detectado. Automação pausada aguardando OK tela azul/DELLMAR.",
            {"timeoutSec": timeout_s, "confirmationKey": DEFAULT_CONFIRMATION_KEY},
        )
        await emit_warn(
            self.emit,
            run_id,
            "rodopar_pdf.manual_login_confirmation_requested",
            "Aguardando confirmação para continuar os passos do Rodopar PDF.",
            {"timeoutSec": timeout_s, "confirmationKey": DEFAULT_CONFIRMATION_KEY},
        )

        while time.time() <= deadline:
            if page.is_closed():
                raise RuntimeError("Pagina HTML5 fechada enquanto aguardava login Rodopar.")

            if consume_manual_confirmation(self.settings, run_id, DEFAULT_CONFIRMATION_KEY):
                await emit_step(
                    self.emit,
                    run_id,
                    "rodopar_pdf.manual_login_confirmed",
                    "Login Rodopar/DELLMAR confirmado pelo usuário. Iniciando passos do PDF.",
                    {"confirmationKey": DEFAULT_CONFIRMATION_KEY},
                )
                return

            await asyncio.sleep(0.5)

        raise RuntimeError(
            "Tempo esgotado aguardando confirmação manual do login Rodopar/DELLMAR antes dos passos de PDF."
        )

    async def _resolve_rows(
        self,
        config: dict[str, Any],
        request: RunStartRequest,
        run_id: str,
    ) -> list[dict[str, Any]]:
        configured_rows = config.get("rows")
        if isinstance(configured_rows, list) and configured_rows:
            return self._dedupe_rows(configured_rows, config)

        raw_ctes = str(config.get("ctes") or "").strip()
        rows_from_env = self._parse_cte_list(raw_ctes, config)
        if rows_from_env:
            return rows_from_env

        request_row = self._row_from_request(request, config)
        if request_row:
            return [request_row]

        if config.get("readConsulta") is False:
            return []

        try:
            consulta = read_consulta_rows(config, self.settings.backend_root.parent)
        except Exception as exc:
            await emit_warn(
                self.emit,
                run_id,
                "rodopar_pdf.consulta_failed",
                f"Não consegui carregar CONSULTA para Rodopar PDF: {exc}",
            )
            return []

        await emit_step(
            self.emit,
            run_id,
            "rodopar_pdf.consulta",
            f"CONSULTA carregada para Rodopar PDF: {consulta.valid_rows} registro(s).",
            {"sourceFile": consulta.source_file, "sheetName": consulta.sheet_name},
        )
        return self._dedupe_rows(consulta.records, config)

    def _row_from_request(
        self,
        request: RunStartRequest,
        config: dict[str, Any],
    ) -> dict[str, Any] | None:
        cte_row = self._normalize_row(str(request.sample_cte or ""), config)
        if cte_row:
            return cte_row

        filial = str(request.sample_filial or "").strip()
        serie = str(request.sample_serie or "").strip()
        documento = str(request.sample_documento or "").strip()
        if not filial or not documento:
            return None
        return {
            "filial": filial,
            "serie": serie or str(config.get("defaultSerie") or "10").strip(),
            "documento": documento,
        }

    def _parse_cte_list(
        self,
        raw_value: str,
        config: dict[str, Any],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in re.split(r"[\r\n,;]+", raw_value):
            row = self._normalize_row(item, config)
            if row:
                rows.append(row)
        return self._dedupe_rows(rows, config)

    def _dedupe_rows(
        self,
        rows: list[Any],
        config: dict[str, Any],
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for value in rows:
            row = self._normalize_row(value, config)
            if not row:
                continue
            key = f"{row['filial']}|{row['serie']}|{row['documento']}"
            if key in seen:
                continue
            seen.add(key)
            out.append(row)
        return out

    def _normalize_row(
        self,
        value: Any,
        config: dict[str, Any],
    ) -> dict[str, Any] | None:
        if isinstance(value, str):
            parts = [part for part in re.split(r"[-/\s]+", value.strip()) if part]
            if len(parts) == 3:
                return {"filial": parts[0], "serie": parts[1], "documento": parts[2]}
            if len(parts) == 1 and parts[0].isdigit():
                return {
                    "filial": str(config.get("defaultFilial") or "").strip(),
                    "serie": str(config.get("defaultSerie") or "10").strip(),
                    "documento": parts[0],
                }
            return None

        if not isinstance(value, dict):
            return None
        filial = self._first_text(value, "filial", "FILIAL") or str(config.get("defaultFilial") or "")
        serie = self._first_text(value, "serie", "SERIE") or str(config.get("defaultSerie") or "10")
        documento = self._first_text(value, "documento", "DOCUMENTO", "nCT", "NCT", "numeroCte")
        if not filial or not serie or not documento:
            return None
        return {**value, "filial": filial, "serie": serie, "documento": documento}

    def _first_text(self, row: dict[str, Any], *keys: str) -> str:
        for key in keys:
            text = str(row.get(key) or "").strip()
            if text:
                return text
        return ""

    def _positive_int(self, value: Any, fallback: int) -> int:
        try:
            parsed = int(str(value).strip())
        except (TypeError, ValueError):
            return fallback
        return parsed if parsed > 0 else fallback

    def _rodopar_steps(self, config: dict[str, Any]) -> list[StepDefinition]:
        capture_file = self._resolve(str(config.get("captureFile") or ""))
        if capture_file.is_file():
            steps = load_pointer_map_steps(capture_file)
            if steps:
                return self._with_step_delay(steps, config)
            return []
        if config.get("captureFile"):
            return []
        return self._with_step_delay(self.repository.list().steps, config)

    async def _configure_empty_map(
        self,
        page: Page,
        config: dict[str, Any],
        run_id: str,
    ) -> list[StepDefinition]:
        await emit_warn(
            self.emit,
            run_id,
            "rodopar_pdf.empty_map",
            "Mapa Rodopar PDF vazio. Cadastre os pontos pelo overlay e clique em Finalizar.",
        )
        overlay = RodoparReplayOverlay(self.settings, config)
        steps = await overlay.configure_empty(page, run_id, [])
        return self._with_step_delay(steps, config)

    def _with_step_delay(
        self,
        steps: list[StepDefinition],
        config: dict[str, Any],
    ) -> list[StepDefinition]:
        return [
            step.model_copy(update={"delay_ms": max(step.delay_ms or 0, self._delay_for_step(step, config))})
            for step in steps
        ]

    def _delay_for_step(self, step: StepDefinition, config: dict[str, Any]) -> int:
        base_delay = self._positive_int(config.get("stepDelayMs"), 3000)
        input_delay = self._positive_int(config.get("inputStepDelayMs"), base_delay)
        sensitive_delay = self._positive_int(config.get("sensitiveStepDelayMs"), max(base_delay, 4500))
        label = step.label.upper()
        if step.action == "fill" or "INPUT" in label:
            return input_delay
        if re.search(
            r"FATURAMENTO|MOVIMENTACAO|CONHECIMENTO|IMPRIMIR|SALVAR|EXPORT|WEBFILE|"
            r"PASTA|CONFIRM|SOBRESCREVER|DELLMAR|INICIO_LOOP|EFETUAR|BUSCAR|VOLTAR",
            label,
        ):
            return sensitive_delay
        return base_delay

    def _step_window(self, config: dict[str, Any], steps: list[StepDefinition]) -> tuple[int, int, int]:
        first_step = self._positive_int(config.get("firstStartStep"), DEFAULT_FIRST_START_STEP)
        default_loop_start = find_step_number(steps, r"INPUT_(CTRC|CRTC)_INICIAL") or DEFAULT_LOOP_START_STEP
        loop_point = next((step.number for step in steps if step.loop_point), None)
        default_loop_end = loop_point or find_step_number(steps, r"^INICIO_LOOP$") or DEFAULT_LOOP_END_STEP
        loop_start = self._positive_int(config.get("loopStartStep"), default_loop_start)
        loop_end = self._positive_int(config.get("loopEndStep"), default_loop_end)
        return first_step, loop_start, loop_end

    def _resolve(self, value: str) -> Path:
        path = Path(str(value))
        return path if path.is_absolute() else self.settings.backend_root.parent / path
