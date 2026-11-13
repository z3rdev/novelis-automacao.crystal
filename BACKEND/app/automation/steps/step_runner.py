import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path

from playwright.async_api import Page

from app.automation.steps.ocr_matcher import OcrMatch, find_text_prefix, list_detected_lines
from app.automation.steps.overlay_visibility import set_overlay_visible
from app.automation.steps.template_matcher import best_effort_match, locate_template
from app.config.settings import Settings
from app.domain.models import RunStartRequest, StepDefinition
from app.services.browser_driver import BrowserDriver

Emit = Callable[..., Awaitable[object]]
PauseCheck = Callable[[], Awaitable[bool]]

TEMPLATE_MIN_CONFIDENCE = 0.80
TEMPLATE_SEARCH_RADIUS = 220
TEMPLATE_LOCATE_ATTEMPTS = 4
TEMPLATE_RETRY_WAIT_MS = 500
PAUSE_POLL_SECONDS = 0.15

OCR_MIN_CONFIDENCE = 40.0
OCR_SEARCH_RADIUS = 260
OCR_SCROLL_ATTEMPTS = 8
OCR_SCROLL_AMOUNT = 140
OCR_SCROLL_WAIT_MS = 350
OCR_SCROLL_CLICKS_PER_ATTEMPT = 3
OCR_SCROLL_TO_TOP_CLICKS = 25

SHORTCUT_KEY_ALIASES = {
    "ctrl": "Control",
    "control": "Control",
    "alt": "Alt",
    "option": "Alt",
    "shift": "Shift",
    "cmd": "Meta",
    "command": "Meta",
    "meta": "Meta",
    "win": "Meta",
    "windows": "Meta",
    "esc": "Escape",
    "escape": "Escape",
    "enter": "Enter",
    "return": "Enter",
    "space": "Space",
    "del": "Delete",
    "delete": "Delete",
    "tab": "Tab",
}


class StepRunner:
    def __init__(self, settings: Settings, emit: Emit) -> None:
        self.settings = settings
        self.emit = emit
        self._template_cache: dict[str, bytes] = {}

    async def execute(
        self,
        step: StepDefinition,
        request: RunStartRequest,
        browser: BrowserDriver | None,
        run_id: str,
        page: Page | None = None,
        pause_check: PauseCheck | None = None,
    ) -> None:
        if not step.enabled:
            await self.emit(
                f"Passo {step.number} ignorado: {step.label}",
                run_id=run_id,
                kind="step.skipped",
                payload={"step": step.model_dump(mode="json")},
            )
            return

        event_payload = {"step": step.model_dump(mode="json")}
        if step.action == "fill":
            event_payload["inputValue"] = self._input_value(step, request)

        await self.emit(
            f"Executando passo {step.number}: {step.label}",
            run_id=run_id,
            kind="step.started",
            payload=event_payload,
        )

        if request.dry_run:
            await self._sleep_with_pause(self._delay_seconds(step), pause_check)
        elif browser is None:
            raise RuntimeError("BrowserDriver obrigatório para execução real.")
        else:
            await self._execute_browser_action(step, request, browser, page, run_id)
            await self._sleep_with_pause(self._delay_seconds(step), pause_check)

        await self.emit(
            f"Passo {step.number} concluído: {step.label}",
            run_id=run_id,
            kind="step.completed",
            payload={"stepNumber": step.number},
        )

    async def _execute_browser_action(
        self,
        step: StepDefinition,
        request: RunStartRequest,
        browser: BrowserDriver,
        page: Page | None,
        run_id: str,
    ) -> None:
        active_page = page or browser.page
        if step.action == "wait":
            return
        if step.action == "screenshot":
            await active_page.screenshot(type="png", full_page=False)
            return
        if step.action == "click":
            x, y = await self._resolve_click_point(active_page, step, run_id)
            await self._click(active_page, x, y, self._reliable_click(step))
            return
        if step.action == "shortcut":
            combo = self._normalize_shortcut(step.shortcut or "")
            if not combo:
                raise RuntimeError(f"Passo {step.number} ({step.label}) não tem atalho configurado.")
            await active_page.keyboard.press(combo)
            return
        if step.action == "ocr_click":
            x, y = await self._resolve_ocr_click_point(active_page, step, run_id)
            await self._click(active_page, x, y, self._reliable_click(step))
            return
        if step.action == "fill":
            text = await self._fill_remote_input(active_page, step, request, run_id)
            if text:
                await self.emit(
                    f"Campo {step.label} preenchido: {text}",
                    run_id=run_id,
                    kind="step.input_typed",
                    payload={"stepNumber": step.number, "label": step.label, "value": text},
                )
            return
        raise RuntimeError(f"Ação de passo não suportada: {step.action}")

    async def _fill_remote_input(
        self,
        page: Page,
        step: StepDefinition,
        request: RunStartRequest,
        run_id: str,
    ) -> str:
        x, y = await self._resolve_click_point(page, step, run_id)
        await self._click(page, x, y, reliable=True)
        text = self._input_value(step, request).strip()
        if not text:
            return ""
        await page.wait_for_timeout(250)
        await self._clear_focused_input(page)
        await page.wait_for_timeout(80)
        await page.keyboard.type(text, delay=70)
        await page.wait_for_timeout(180)
        return text

    async def _resolve_click_point(self, page: Page, step: StepDefinition, run_id: str) -> tuple[int, int]:
        template_bytes = self._load_template(step)
        if template_bytes is None:
            return step.x, step.y

        for attempt in range(1, TEMPLATE_LOCATE_ATTEMPTS + 1):
            await set_overlay_visible(page, False)
            await page.wait_for_timeout(30)
            try:
                screenshot = await page.screenshot(type="png")
            except Exception:
                return step.x, step.y
            finally:
                await set_overlay_visible(page, True)
            match = locate_template(
                screenshot,
                template_bytes,
                center=(step.x, step.y),
                search_radius=TEMPLATE_SEARCH_RADIUS,
                min_confidence=TEMPLATE_MIN_CONFIDENCE,
            )
            if match is not None:
                return match.x, match.y
            best = best_effort_match(screenshot, template_bytes, center=(step.x, step.y), search_radius=TEMPLATE_SEARCH_RADIUS)
            best_text = (
                f"melhor parecido encontrado teve {best.confidence * 100:.0f}% de confiança "
                f"(precisa de {TEMPLATE_MIN_CONFIDENCE * 100:.0f}%)"
                if best is not None
                else "nada parecido encontrado na tela"
            )
            if attempt < TEMPLATE_LOCATE_ATTEMPTS:
                await self.emit(
                    f"Não encontrei o alvo do passo {step.number} ({step.label}) na posição gravada "
                    f"({best_text}). Tentando novamente ({attempt}/{TEMPLATE_LOCATE_ATTEMPTS}).",
                    run_id=run_id,
                    kind="step.locate_retry",
                    payload={
                        "stepNumber": step.number,
                        "label": step.label,
                        "attempt": attempt,
                        "bestConfidence": best.confidence if best is not None else None,
                    },
                )
                await page.wait_for_timeout(TEMPLATE_RETRY_WAIT_MS)

        raise RuntimeError(
            f"Não localizei o alvo do passo {step.number} ({step.label}) na tela atual após "
            f"{TEMPLATE_LOCATE_ATTEMPTS} tentativas ({best_text}). Parei para não clicar no lugar errado."
        )

    async def _resolve_ocr_click_point(self, page: Page, step: StepDefinition, run_id: str) -> tuple[int, int]:
        prefix = (step.ocr_text or "").strip()
        if not prefix:
            raise RuntimeError(f"Passo {step.number} ({step.label}) não tem texto OCR configurado.")

        await self._scroll_to_top_for_ocr(page, step, run_id)

        last_seen: list[str] = []
        for attempt in range(1, OCR_SCROLL_ATTEMPTS + 1):
            match, seen = await self._search_ocr_text(page, step, prefix)
            if match is not None:
                await self.emit(
                    f"Texto identificado para o passo {step.number} ({step.label}): \"{match.text}\" "
                    f"(confiança {match.confidence:.0f}%).",
                    run_id=run_id,
                    kind="step.ocr_text_found",
                    payload={
                        "stepNumber": step.number,
                        "label": step.label,
                        "text": match.text,
                        "confidence": match.confidence,
                        "x": match.x,
                        "y": match.y,
                    },
                )
                return (match.x, match.y)
            last_seen = seen
            seen_text = "; ".join(seen) if seen else "(nada legível perto do ponto de referência)"
            if attempt < OCR_SCROLL_ATTEMPTS:
                await self.emit(
                    f"Não encontrei texto começando com \"{prefix}\" para o passo {step.number} "
                    f"({step.label}). Texto lido nessa tentativa: {seen_text}. "
                    f"Rolando a tela e tentando de novo ({attempt}/{OCR_SCROLL_ATTEMPTS}).",
                    run_id=run_id,
                    kind="step.ocr_scroll_retry",
                    payload={"stepNumber": step.number, "label": step.label, "attempt": attempt, "textSeen": seen},
                )
                await self._scroll_for_ocr(page, step)
                await page.wait_for_timeout(OCR_SCROLL_WAIT_MS)

        seen_text = "; ".join(last_seen) if last_seen else "(nada legível perto do ponto de referência)"
        raise RuntimeError(
            f"Não encontrei texto começando com \"{prefix}\" para o passo {step.number} ({step.label}) "
            f"mesmo após rolar a tela {OCR_SCROLL_ATTEMPTS} vezes. Último texto lido: {seen_text}. "
            "Parei para não clicar no lugar errado."
        )

    async def _scroll_to_top_for_ocr(self, page: Page, step: StepDefinition, run_id: str) -> None:
        if step.scroll_up_x is None or step.scroll_up_y is None:
            return
        # The target text can be above the list's current scroll position (e.g. left
        # scrolled down by a previous step), and the retry loop below only scrolls
        # downward. Reset to the top first so a single top-to-bottom sweep can always
        # reach it, regardless of where the list happened to start.
        await self.emit(
            f"Rolando a lista até o topo antes de procurar o texto do passo {step.number} ({step.label}).",
            run_id=run_id,
            kind="step.ocr_scroll_to_top",
            payload={"stepNumber": step.number, "label": step.label},
        )
        for _ in range(OCR_SCROLL_TO_TOP_CLICKS):
            try:
                await page.mouse.click(step.scroll_up_x, step.scroll_up_y)
            except Exception:
                pass
            await page.wait_for_timeout(60)

    async def _scroll_for_ocr(self, page: Page, step: StepDefinition) -> None:
        if step.scroll_x is not None and step.scroll_y is not None:
            # A taught scrollbar-arrow position is a plain click, which this remote screen
            # already forwards reliably — far more trustworthy than wheel/keyboard scrolling,
            # which some remote-rendered (Citrix/HTML5-style) screens silently drop.
            for _ in range(OCR_SCROLL_CLICKS_PER_ATTEMPT):
                try:
                    await page.mouse.click(step.scroll_x, step.scroll_y)
                except Exception:
                    pass
                await page.wait_for_timeout(120)
            return

        # No taught scroll button yet: best-effort fallback (focus + PageDown + wheel).
        try:
            await page.mouse.click(step.x, step.y)
        except Exception:
            pass
        await page.wait_for_timeout(80)
        try:
            await page.keyboard.press("PageDown")
        except Exception:
            pass
        try:
            await page.mouse.move(step.x, step.y)
            await page.mouse.wheel(0, OCR_SCROLL_AMOUNT)
        except Exception:
            pass

    async def _search_ocr_text(
        self, page: Page, step: StepDefinition, prefix: str
    ) -> tuple[OcrMatch | None, list[str]]:
        await set_overlay_visible(page, False)
        await page.wait_for_timeout(30)
        try:
            screenshot = await page.screenshot(type="png")
        except Exception:
            return None, []
        finally:
            await set_overlay_visible(page, True)

        left = max(0, step.x - OCR_SEARCH_RADIUS)
        top = max(0, step.y - OCR_SEARCH_RADIUS)
        region = (left, top, OCR_SEARCH_RADIUS * 2, OCR_SEARCH_RADIUS * 2)
        try:
            match = find_text_prefix(screenshot, prefix, region=region, min_confidence=OCR_MIN_CONFIDENCE)
            if match is None:
                match = find_text_prefix(screenshot, prefix, region=None, min_confidence=OCR_MIN_CONFIDENCE)
            seen = [] if match is not None else list_detected_lines(screenshot, region=region)
        except Exception:
            # A transient OCR-engine failure (e.g. memory pressure) is just a failed attempt,
            # not proof the text is absent — let the scroll-and-retry loop keep going.
            return None, []
        return match, seen

    def _load_template(self, step: StepDefinition) -> bytes | None:
        if step.template is None or not step.template.path:
            return None
        cached = self._template_cache.get(step.template.path)
        if cached is not None:
            return cached
        path = self._resolve_template_path(step.template.path)
        if not path.is_file():
            return None
        data = path.read_bytes()
        self._template_cache[step.template.path] = data
        return data

    def _resolve_template_path(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.settings.backend_root.parent / path

    async def _click(self, page: Page, x: int, y: int, reliable: bool = True) -> None:
        await page.mouse.move(x, y, steps=18)
        await page.wait_for_timeout(120)
        await page.mouse.down()
        await page.wait_for_timeout(80)
        await page.mouse.up()
        if reliable:
            await page.wait_for_timeout(150)
            await page.mouse.down()
            await page.wait_for_timeout(80)
            await page.mouse.up()
        await page.wait_for_timeout(150)

    def _input_value(self, step: StepDefinition, request: RunStartRequest) -> str:
        key = (step.input_key or "").strip().lower()
        values = {
            "filial": request.sample_filial,
            "serie": request.sample_serie,
            "documento": request.sample_documento,
            "documento_inicial": request.sample_documento,
            "documento_final": request.sample_documento,
            "cte": request.sample_cte,
            "nome_arquivo": self._ctrc_file_name(request),
        }
        return values.get(key, "")

    async def _clear_focused_input(self, page: Page) -> None:
        await page.wait_for_timeout(120)
        await self._control_a(page)
        await page.wait_for_timeout(60)
        await self._press(page, "Backspace")
        await self._press(page, "Delete")
        await self._press(page, "Home")
        await self._press_many(page, "Delete", 80)
        await self._press(page, "End")
        await self._press_many(page, "Backspace", 80)
        await self._control_a(page)
        await page.wait_for_timeout(40)
        await self._press(page, "Backspace")

    async def _control_a(self, page: Page) -> None:
        try:
            await page.keyboard.down("Control")
            await page.keyboard.press("A")
        except Exception:
            pass
        finally:
            try:
                await page.keyboard.up("Control")
            except Exception:
                pass

    async def _press_many(self, page: Page, key: str, times: int, delay_ms: int = 5) -> None:
        for _ in range(times):
            await self._press(page, key)
            if delay_ms > 0:
                await page.wait_for_timeout(delay_ms)

    async def _press(self, page: Page, key: str) -> None:
        try:
            await page.keyboard.press(key)
        except Exception:
            pass

    def _normalize_shortcut(self, raw: str) -> str:
        parts = [part.strip() for part in raw.replace("-", "+").split("+") if part.strip()]
        if not parts:
            return ""
        normalized = []
        for part in parts:
            alias = SHORTCUT_KEY_ALIASES.get(part.lower())
            if alias:
                normalized.append(alias)
            elif len(part) == 1:
                normalized.append(part.upper())
            else:
                normalized.append(part[:1].upper() + part[1:])
        return "+".join(normalized)

    def _reliable_click(self, step: StepDefinition) -> bool:
        if step.reliable_click is not None:
            return step.reliable_click
        return "FECHAR" not in step.label.upper() and "FECHANDO" not in step.label.upper()

    def _ctrc_file_name(self, request: RunStartRequest) -> str:
        parts = [
            request.sample_filial.strip(),
            request.sample_serie.strip(),
            request.sample_documento.strip(),
        ]
        filled = [part for part in parts if part]
        return f"CTRC_{'-'.join(filled)}" if filled else "CTRC"

    async def _sleep_with_pause(self, seconds: float, pause_check: PauseCheck | None) -> None:
        if pause_check is None:
            await asyncio.sleep(seconds)
            return
        remaining = seconds
        while True:
            if await pause_check():
                await asyncio.sleep(PAUSE_POLL_SECONDS)
                continue
            if remaining <= 0:
                return
            tick = min(PAUSE_POLL_SECONDS, remaining)
            await asyncio.sleep(tick)
            remaining -= tick

    def _delay_seconds(self, step: StepDefinition) -> float:
        delay_ms = step.delay_ms if step.delay_ms is not None else self.settings.pre_step_delay_ms
        return max(0, delay_ms) / 1000
