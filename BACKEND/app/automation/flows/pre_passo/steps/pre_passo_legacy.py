import asyncio
from pathlib import Path
from typing import Any, Callable

from playwright.async_api import Page

from app.automation.flows.flow_events import Emit, emit_step, emit_warn
from app.automation.flows.rodopar_pdf_flow.overlay.editing import edit_overlay_after_replay
from app.automation.flows.rodopar_pdf_flow.overlay.replay_overlay import RodoparReplayOverlay
from app.automation.steps.step_runner import StepRunner
from app.config.settings import Settings
from app.data.consulta_reader import read_consulta_rows
from app.domain.models import RunStartRequest, StepDefinition
from app.services.browser_driver import BrowserDriver
from app.services.step_repository import StepRepository


class PrePassoLegacyFlow:
    def __init__(self, settings: Settings, repository: StepRepository, emit: Emit) -> None:
        self.settings = settings
        self.repository = repository
        self.emit = emit

    async def run_initial(
        self,
        browser: BrowserDriver | None,
        config: dict[str, Any],
        request: RunStartRequest,
        run_id: str,
    ) -> Page | None:
        if request.dry_run:
            await self._dry_run(config, request, run_id, start_step=1)
            return None

        if browser is None:
            raise RuntimeError("BrowserDriver obrigatório para pré-passo real.")

        page = await self._ensure_html5_page(browser, config, run_id)
        if config.get("manualLoginOnly"):
            await self._persist_session(browser, config, run_id)
            return page

        await self._replay(page, browser, config, request, run_id, start_step=1)
        await self._persist_session(browser, config, run_id)
        return page

    async def continue_after_tarifario(
        self,
        page: Page,
        browser: BrowserDriver,
        config: dict[str, Any],
        request: RunStartRequest,
        run_id: str,
    ) -> Page:
        start_step = config.get("replayContinueFromStep") or config.get("replaySteps", 3) + 1
        await emit_step(
            self.emit,
            run_id,
            "pre.continue",
            f"Retomando pre-passo a partir do passo {start_step}.",
        )
        await self._replay(page, browser, config, request, run_id, start_step=start_step)
        return page

    async def run_next_row(
        self,
        page: Page,
        browser: BrowserDriver,
        config: dict[str, Any],
        request: RunStartRequest,
        run_id: str,
    ) -> Page:
        end_step = config.get("replayContinueFromStep") or config.get("replaySteps", 3)
        await emit_step(self.emit, run_id, "pre.next_row", "Executando proxima linha no DataPar.")
        await self._replay(page, browser, config, request, run_id, start_step=6, end_step=end_step)
        return page

    async def replay_range(
        self,
        page: Page,
        browser: BrowserDriver,
        config: dict[str, Any],
        request: RunStartRequest,
        run_id: str,
        start_step: int,
        end_step: int,
        steps_override: list[StepDefinition] | None = None,
        steps_reloader: Callable[[], list[StepDefinition]] | None = None,
    ) -> Page:
        await self._replay(
            page, browser, config, request, run_id, start_step, end_step, steps_override, steps_reloader
        )
        return page

    async def _dry_run(
        self,
        config: dict[str, Any],
        request: RunStartRequest,
        run_id: str,
        start_step: int,
    ) -> None:
        await emit_step(self.emit, run_id, "pre.plan", "Simulando pre-passo legado.")
        runner = StepRunner(self.settings, self.emit)
        request = await self._with_consulta_inputs(config, request, run_id, start_step)
        steps = self._selected_steps(config, request, start_step=start_step)
        for step in steps:
            await runner.execute(step, request, None, run_id)

    async def _ensure_html5_page(
        self,
        browser: BrowserDriver,
        config: dict[str, Any],
        run_id: str,
    ) -> Page:
        await browser.start()
        existing = await self._find_html5_page(browser, timeout_ms=1_000, preferred_page=browser.page)
        if existing:
            await emit_step(self.emit, run_id, "pre.session", "Reutilizando aba HTML5 aberta.")
            return await browser.focus_page(existing)

        session_page = await self._try_reuse_saved_session(browser, config, run_id)
        if session_page:
            return session_page

        await emit_step(self.emit, run_id, "pre.open", "Acessando webcloud16.")
        page = browser.page
        await self._goto_pre_page(
            page,
            str(config.get("url") or self.settings.pre_url),
            config,
            "webcloud16",
        )

        if config.get("manualLogin"):
            return await self._wait_manual_html5(browser, config, run_id)

        return await self._login_datapar(page, browser, config, run_id)

    async def _wait_manual_html5(
        self,
        browser: BrowserDriver,
        config: dict[str, Any],
        run_id: str,
    ) -> Page:
        await emit_warn(
            self.emit,
            run_id,
            "pre.manual_login",
            "Login manual solicitado. Aguardando aba HTML5 abrir.",
        )
        timeout_s = max(30, int(config.get("manualLoginTimeoutSec") or 240))
        deadline = asyncio.get_running_loop().time() + timeout_s
        while asyncio.get_running_loop().time() < deadline:
            found = await self._find_html5_page(browser, timeout_ms=1_000)
            if found:
                return await browser.focus_page(found)
            await asyncio.sleep(1)
        raise RuntimeError("Tempo esgotado aguardando login manual DataPar.")

    async def _login_datapar(
        self,
        page: Page,
        browser: BrowserDriver,
        config: dict[str, Any],
        run_id: str,
    ) -> Page:
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            if attempt > 1:
                await emit_step(
                    self.emit,
                    run_id,
                    "pre.login_retry",
                    f"Tentativa de login {attempt}/{max_attempts}.",
                )
                try:
                    still_has_form = await page.query_selector("#Editbox1")
                except Exception:
                    still_has_form = None
                if not still_has_form:
                    await self._goto_pre_page(
                        page,
                        str(config.get("url") or self.settings.pre_url),
                        config,
                        "webcloud16 reload",
                    )

            await emit_step(self.emit, run_id, "pre.login", "Preenchendo login DataPar.")
            await page.wait_for_selector("#Editbox1", state="visible", timeout=30_000)
            await page.fill("#Editbox1", str(config.get("user") or ""))
            await page.fill("#Editbox2", str(config.get("pass") or ""))
            await page.wait_for_selector("#buttonLogOn", state="visible", timeout=10_000)
            await page.click("#buttonLogOn")

            await emit_step(
                self.emit,
                run_id,
                "pre.login_result",
                "Verificando resultado do login e procurando aba HTML5.",
            )
            html5_page = await self._find_html5_page(browser, timeout_ms=12_000, preferred_page=page)
            if html5_page:
                await self._wait_for_html5_screen(html5_page, config)
                return await browser.focus_page(html5_page)

            await self._save_debug_screenshot(
                page,
                config,
                f"login-attempt-{attempt}.png",
            )
            if attempt < max_attempts:
                await asyncio.sleep(2)

        raise RuntimeError("Login DataPar não abriu a página HTML5 após 3 tentativas.")

    async def _replay(
        self,
        page: Page,
        browser: BrowserDriver,
        config: dict[str, Any],
        request: RunStartRequest,
        run_id: str,
        start_step: int,
        end_step: int | None = None,
        steps_override: list[StepDefinition] | None = None,
        steps_reloader: Callable[[], list[StepDefinition]] | None = None,
    ) -> None:
        runner = StepRunner(self.settings, self.emit)
        request = await self._with_consulta_inputs(config, request, run_id, start_step, end_step, steps_override)
        steps = self._selected_steps(config, request, start_step, end_step, steps_override)
        overlay = RodoparReplayOverlay(self.settings, config)

        async def pause_check() -> bool:
            return await overlay.is_paused(run_id)

        index = 0
        while index < len(steps):
            step = steps[index]
            if config.get("bringToFront"):
                await page.bring_to_front()
            browser.activate_page(page)
            next_index = await overlay.before_step(page, run_id, steps, index, step)
            if next_index is not None:
                index = next_index
                continue
            # The overlay's pause loop inside before_step can edit/reorder/remove steps on
            # disk while we're paused. `steps` is a frozen snapshot taken before the pause,
            # so without a reload here the automation would go on to run whatever step used
            # to be at this position instead of what the user just moved there.
            if steps_reloader is not None:
                steps, index, step = self._resync_steps(
                    steps, index, steps_reloader, config, request, start_step, end_step
                )
            if not step.requires_manual:
                # A manual-pause step already had its real action performed by the user
                # by hand while before_step held the run paused; running the recorded
                # click/OCR on top of that would risk a duplicate or misplaced action.
                await runner.execute(step, request, browser, run_id, page=page, pause_check=pause_check)
            next_index = await overlay.after_step(page, run_id, steps, index, step)
            if next_index is not None:
                index = next_index
                continue
            index += 1
        if config.get("replayOverlayEditAfterReplay"):
            edit_steps = steps_override if steps_override is not None else self.repository.list().steps
            await edit_overlay_after_replay(overlay, page, run_id, [step for step in edit_steps if step.enabled])

    def _resync_steps(
        self,
        steps: list[StepDefinition],
        index: int,
        steps_reloader: Callable[[], list[StepDefinition]],
        config: dict[str, Any],
        request: RunStartRequest,
        start_step: int,
        end_step: int | None,
    ) -> tuple[list[StepDefinition], int, StepDefinition]:
        try:
            fresh_source = steps_reloader()
        except Exception:
            fresh_source = None
        if fresh_source:
            resynced = self._selected_steps(config, request, start_step, end_step, fresh_source)
            if resynced:
                steps = resynced
                index = min(index, len(steps) - 1)
        return steps, index, steps[index]

    async def _with_consulta_inputs(
        self,
        config: dict[str, Any],
        request: RunStartRequest,
        run_id: str,
        start_step: int,
        end_step: int | None = None,
        steps_override: list[StepDefinition] | None = None,
    ) -> RunStartRequest:
        selected = self._selected_steps(config, request, start_step, end_step, steps_override)
        needs_filial = self._needs_sheet_value(config, request, selected, "filial")
        needs_documento = self._needs_sheet_value(config, request, selected, "documento")
        if not needs_filial and not needs_documento:
            return request

        try:
            consulta = read_consulta_rows(config, self.settings.backend_root.parent)
        except Exception as exc:
            await emit_warn(
                self.emit,
                run_id,
                "pre.consulta_failed",
                f"Não consegui carregar CONSULTA para filial/documento: {exc}",
            )
            return request

        row = self._consulta_row(consulta.records, config)
        if not row:
            await emit_warn(self.emit, run_id, "pre.consulta_empty", "CONSULTA sem linha valida para pre-passo.")
            return request

        updates: dict[str, str] = {}
        if needs_filial:
            updates["sample_filial"] = str(row.get("filial") or "")
        if needs_documento:
            updates["sample_documento"] = str(row.get("documento") or "")
        if not any(updates.values()):
            return request

        await emit_step(
            self.emit,
            run_id,
            "pre.consulta",
            "Filial/documento carregados da CONSULTA para o pre-passo.",
            {
                "sourceFile": consulta.source_file,
                "sheetName": consulta.sheet_name,
                "filial": updates.get("sample_filial") or request.sample_filial,
                "documento": updates.get("sample_documento") or request.sample_documento,
            },
        )
        return request.model_copy(update=updates)

    async def _try_reuse_saved_session(
        self,
        browser: BrowserDriver,
        config: dict[str, Any],
        run_id: str,
    ) -> Page | None:
        if not config.get("reuseSessionFirst"):
            return None

        await emit_step(self.emit, run_id, "pre.session", "Tentando reaproveitar sessao salva.")
        page = browser.page
        try:
            await self._goto_pre_page(
                page,
                str(config.get("html5Url") or self.settings.pre_html5_url),
                config,
                "html5 sessao salva",
                attempts=1,
            )
            html5_page = await self._find_html5_page(browser, timeout_ms=9_000, preferred_page=page)
            if not html5_page:
                await emit_warn(
                    self.emit,
                    run_id,
                    "pre.session_expired",
                    "Sessão salva indisponível. Voltando para fluxo de login.",
                )
                return None
            await self._wait_for_html5_screen(html5_page, config)
            await emit_step(self.emit, run_id, "pre.session", "Sessão reaproveitada com sucesso.")
            return await browser.focus_page(html5_page)
        except Exception:
            await emit_warn(
                self.emit,
                run_id,
                "pre.session_expired",
                "Sessão salva inválida/expirada. Voltando para fluxo de login.",
            )
            return None

    async def _find_html5_page(
        self,
        browser: BrowserDriver,
        timeout_ms: int = 8_000,
        preferred_page: Page | None = None,
    ) -> Page | None:
        deadline = asyncio.get_running_loop().time() + (timeout_ms / 1000)
        while asyncio.get_running_loop().time() < deadline:
            if self._is_html5_page_ready(preferred_page):
                return preferred_page

            for page in browser.context.pages:
                if self._is_html5_page_ready(page):
                    return page
            await asyncio.sleep(0.3)
        return None

    async def _wait_for_html5_screen(self, page: Page, config: dict[str, Any]) -> None:
        try:
            await page.wait_for_url("**/software/html5.html", timeout=30_000)
        except Exception:
            if not self._is_html5_page_ready(page):
                await self._goto_pre_page(
                    page,
                    str(config.get("html5Url") or self.settings.pre_html5_url),
                    {**config, "navigationTimeoutMs": 30_000, "navigationRetries": 1},
                    "html5",
                    attempts=1,
                    timeout_ms=30_000,
                )

        await asyncio.sleep(1.5)
        if not self._is_html5_page_ready(page):
            raise RuntimeError(f"Tela HTML5 não ativa. URL atual: {self._page_url(page) or 'about:blank'}")

    async def _goto_pre_page(
        self,
        page: Page,
        url: str,
        config: dict[str, Any],
        label: str,
        *,
        attempts: int | None = None,
        timeout_ms: int | None = None,
    ) -> None:
        timeout = max(10_000, int(timeout_ms or config.get("navigationTimeoutMs") or 45_000))
        total_attempts = max(1, int(attempts or config.get("navigationRetries") or 3))
        last_error: Exception | None = None

        for attempt in range(1, total_attempts + 1):
            try:
                await page.goto(url, wait_until="commit", timeout=timeout)
                return
            except Exception as exc:
                last_error = exc
                await self._stop_pending_navigation(page)
                if attempt < total_attempts:
                    await asyncio.sleep(2)

        current_url = self._page_url(page) or "about:blank"
        raise RuntimeError(
            f"Falha ao abrir {label} após {total_attempts} tentativa(s). "
            f"URL={url}. URL atual={current_url}. {last_error}"
        )

    async def _stop_pending_navigation(self, page: Page) -> None:
        if self._is_page_closed(page):
            return
        try:
            await page.evaluate("window.stop()")
        except Exception:
            pass
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=3_000)
        except Exception:
            pass

    async def _save_debug_screenshot(
        self,
        page: Page,
        config: dict[str, Any],
        file_name: str,
    ) -> None:
        if not config.get("saveDebugShots") or self._is_page_closed(page):
            return
        debug_dir = Path(str(config.get("debugDir") or "captures/debug"))
        if not debug_dir.is_absolute():
            debug_dir = self.settings.backend_root.parent / debug_dir
        debug_dir.mkdir(parents=True, exist_ok=True)
        try:
            await page.screenshot(path=str(debug_dir / file_name), full_page=True)
        except Exception:
            pass

    def _is_html5_page_ready(self, page: Page | None) -> bool:
        return not self._is_page_closed(page) and "/software/html5.html" in self._page_url(page)

    @staticmethod
    def _is_page_closed(page: Page | None) -> bool:
        try:
            return page is None or page.is_closed()
        except Exception:
            return True

    def _page_url(self, page: Page | None) -> str:
        if self._is_page_closed(page):
            return ""
        try:
            return page.url
        except Exception:
            return ""

    def _needs_sheet_value(
        self,
        config: dict[str, Any],
        request: RunStartRequest,
        steps,
        key: str,
    ) -> bool:
        current_value = request.sample_filial if key == "filial" else request.sample_documento
        if current_value:
            return False

        enabled = config.get("fillFilialFromSheet") if key == "filial" else config.get("fillDocumentoFromSheet")
        step_number = config.get("filialStepNumber") if key == "filial" else config.get("documentoStepNumber")
        if not enabled:
            return False

        return any(
            step.action == "fill"
            and (
                (step.input_key or "").strip().lower() == key
                or step.number == int(step_number or 0)
            )
            for step in steps
        )

    def _consulta_row(
        self,
        records: list[dict[str, Any]],
        config: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not records:
            return None

        filial_index = int(config.get("filialRowIndex") or 0)
        documento_index = int(config.get("documentoRowIndex") or filial_index)
        index = max(0, documento_index if documento_index else filial_index)
        if index >= len(records):
            return records[0]
        return records[index]

    def _selected_steps(
        self,
        config: dict[str, Any],
        request: RunStartRequest,
        start_step: int,
        end_step: int | None = None,
        steps_override: list[StepDefinition] | None = None,
    ):
        source_steps = steps_override if steps_override is not None else self.repository.list().steps
        steps = [step for step in source_steps if step.enabled]
        if end_step is None:
            end_step = start_step + int(config.get("replaySteps") or request.max_steps or len(steps)) - 1
        if request.max_steps and start_step == 1:
            end_step = min(end_step, request.max_steps)
        return [step for step in steps if start_step <= step.number <= end_step]

    async def _persist_session(
        self,
        browser: BrowserDriver,
        config: dict[str, Any],
        run_id: str,
    ) -> None:
        if not config.get("saveSessionState"):
            return
        state_file = Path(str(config.get("sessionStateFile") or "captures/session-state.json"))
        if not state_file.is_absolute():
            state_file = self.settings.backend_root.parent / state_file
        state_file.parent.mkdir(parents=True, exist_ok=True)
        await browser.save_storage_state(str(state_file))
        await emit_step(self.emit, run_id, "pre.session_saved", f"Sessão salva em {state_file}.")
