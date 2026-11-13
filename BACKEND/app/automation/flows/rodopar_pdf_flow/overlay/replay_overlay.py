import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from playwright.async_api import Page

from app.automation.steps.overlay_visibility import set_overlay_visible
from app.automation.steps.pointer_map_steps import action_for_label, load_pointer_map_steps
from app.config.settings import Settings
from app.domain.models import StepDefinition, StepTemplate, Viewport
from app.infrastructure.json_store import read_json, write_json
from app.services.overlay_bridge import (
    peek_overlay_paused,
    pop_overlay_command,
    pop_recorded_clicks,
    push_recorded_click,
    set_overlay_paused,
    set_overlay_state,
)

TEMPLATE_WIDTH = 160
TEMPLATE_HEIGHT = 70

_RECORDING_SCRIPT = """() => {
  if (window.__rodoparRecordingBound) return;
  window.__rodoparRecordingBound = true;
  window.__rodoparRecordingActive = false;
  document.addEventListener("click", event => {
    if (!window.__rodoparRecordingActive) return;
    if (typeof window.__rodoparReportClick === "function") {
      window.__rodoparReportClick(Math.round(event.clientX), Math.round(event.clientY));
    }
  }, true);
}"""


class RodoparReplayOverlay:
    def __init__(self, settings: Settings, config: dict[str, Any]) -> None:
        self.settings = settings
        self.enabled = bool(config.get("replayOverlayEnabled"))
        self.capture_file = self._resolve(str(config.get("captureFile") or ""))
        self.status = "Overlay pronto."
        self.current_index = -1
        self.current_step: StepDefinition | None = None
        self._recording_bound = False
        self.recording = False

    async def before_step(
        self, page: Page, run_id: str, steps: list[StepDefinition], index: int, step: StepDefinition
    ) -> int | None:
        if not self.enabled: return None
        self.current_index = index
        self.current_step = step
        if step.requires_manual:
            await self._set_paused(run_id, True)
            self.status = (
                f"AÇÃO MANUAL: faça a ação na tela para o passo {step.number} - {step.label} "
                "e clique em Retomar para continuar."
            )
            await self.update(run_id, steps)
            return await self._wait_controls(page, run_id, steps, index, step, paused_rendered=True)
        self.status = f"Proximo passo: {step.number} - {step.label}."
        await self.update(run_id, steps)
        return await self._wait_controls(page, run_id, steps, index, step)

    async def after_step(
        self, page: Page, run_id: str, steps: list[StepDefinition], index: int, step: StepDefinition
    ) -> int | None:
        if not self.enabled: return None
        self.current_index = index
        self.current_step = step
        self.status = f"Passo {step.number} executado."
        await self.update(run_id, steps)
        return await self._read_once(page, run_id, steps, index, step)

    async def configure_empty(self, page: Page, run_id: str, steps: list[StepDefinition]) -> list[StepDefinition]:
        if not self.enabled: return steps
        self.current_index = -1
        self.current_step = None
        self.status = "Mapa vazio. Use Novo, Salvar ou Fechar."
        await self.update(run_id, steps)
        while True:
            control = await self._control(run_id)
            action = control.get("action")
            if isinstance(action, dict):
                action_type = str(action.get("type") or "").lower()
                if action_type == "save":
                    self._renumber_steps(steps)
                    await self.update(run_id, steps, "Mapa salvo. O overlay continua aberto.")
                if action_type == "finish":
                    self._renumber_steps(steps)
                    self.status = "Cadastro finalizado."
                    await self.update(run_id, steps)
                    return steps
                if action_type == "cancel":
                    await self.update(run_id, steps, "Captura cancelada.")
                if action_type == "clear":
                    self._clear_steps(steps)
                    self.status = "Mapa limpo."
                    await self.update(run_id, steps)
                if action_type == "select":
                    self._select_step(steps, action)
                    await self.update(run_id, steps)
                if action_type == "loop" and self.current_step:
                    marked = self._toggle_loop_point(steps, self.current_step)
                    text = "marcado" if marked else "desmarcado"
                    await self.update(run_id, steps, f"Ponto de loop {text}: {self.current_step.number}.")
                if action_type == "create":
                    step = await self._create_step(page, steps, action)
                    self.current_step = step
                    self.status = f"Ponto criado: {step.number} - {step.label}."
                    await self.update(run_id, steps)
                if action_type == "remove" and self.current_step:
                    await self._handle_remove(steps, action, self.current_step)
                    await self.update(run_id, steps)
                if action_type == "capture" and self.current_step:
                    target = self._target_step(steps, action, self.current_step)
                    await self._apply_capture(page, target, action)
                    self.status = f"Ponto ajustado: {target.number} - {target.label} em {target.x},{target.y}."
                    await self.update(run_id, steps)
                if action_type == "capture_scroll" and self.current_step:
                    target = self._target_step(steps, action, self.current_step)
                    self._apply_scroll_capture(page, target, action)
                    self.status = (
                        f"Rolagem ajustada: {target.number} - {target.label} em {target.scroll_x},{target.scroll_y}."
                    )
                    await self.update(run_id, steps)
                if action_type == "capture_scroll_up" and self.current_step:
                    target = self._target_step(steps, action, self.current_step)
                    self._apply_scroll_up_capture(page, target, action)
                    self.status = (
                        f"Rolagem (subir) ajustada: {target.number} - {target.label} "
                        f"em {target.scroll_up_x},{target.scroll_up_y}."
                    )
                    await self.update(run_id, steps)
                if action_type == "edit" and self.current_step:
                    target = self._target_step(steps, action, self.current_step)
                    self._apply_edit(page, target, action)
                    self.status = f"Passo editado: {target.number} - {target.label}."
                    await self.update(run_id, steps)
                if action_type in {"up", "down"} and self.current_step:
                    await self._handle_reorder(
                        run_id, steps, action, self.current_step, -1 if action_type == "up" else 1
                    )
                if action_type == "reorder":
                    self._apply_reorder(action)
                    await self.update(run_id, steps)
                if action_type == "start_recording":
                    await self.set_recording(page, run_id, True)
                    await self.update(
                        run_id, steps, "Gravando automaticamente: cada clique na tela vira um passo novo."
                    )
                if action_type == "stop_recording":
                    await self.set_recording(page, run_id, False)
                    await self.update(run_id, steps, "Gravação pausada.")
            await self._drain_recorded_clicks(page, run_id, steps)
            await asyncio.sleep(0.45)

    async def update(self, run_id: str, steps: list[StepDefinition], status: str = "") -> None:
        if not self.enabled: return
        if status:
            self.status = status
        set_overlay_state(run_id, self._payload(self._display_steps(steps)))

    def _display_steps(self, steps: list[StepDefinition]) -> list[StepDefinition]:
        # `steps` is frequently just a WINDOW of the full on-disk map used for actual
        # replay execution (see _renumber_steps), and it can go stale immediately after
        # a disk-only mutation like a drag reorder or an edit to a step outside that
        # window. The UI should always reflect the true, persisted order, so read fresh
        # from disk for display whenever a capture file is available.
        if not self.capture_file:
            return steps
        disk_steps = load_pointer_map_steps(self.capture_file)
        return disk_steps or steps

    async def _wait_controls(
        self,
        page: Page,
        run_id: str,
        steps: list[StepDefinition],
        index: int,
        step: StepDefinition,
        paused_rendered: bool = False,
    ) -> int | None:
        while True:
            override = await self._read_once(page, run_id, steps, index, step)
            if override is not None: return override
            await self._drain_recorded_clicks(page, run_id, steps)
            control = await self._control(run_id)
            if not control.get("paused"):
                return None
            if not paused_rendered:
                await self.update(run_id, steps, "Pausado pelo overlay.")
                paused_rendered = True
            await asyncio.sleep(0.45)

    async def _read_once(
        self, page: Page, run_id: str, steps: list[StepDefinition], index: int, step: StepDefinition
    ) -> int | None:
        control = await self._control(run_id)
        action = control.get("action")
        if not isinstance(action, dict): return None
        action_type = str(action.get("type") or "").lower()
        if action_type == "save":
            self._renumber_steps(steps)
            await self.update(run_id, steps, "Mapa salvo. Pode continuar editando.")
            return None
        if action_type == "finish":
            self._renumber_steps(steps)
            await self._set_paused(run_id, False)
            self.status = "Overlay fechado."
            await self.update(run_id, steps)
            return len(steps)
        if action_type == "back":
            await self._set_paused(run_id, False)
            return max(0, index - 1)
        if action_type == "skip":
            await self._set_paused(run_id, False)
            return min(len(steps), index + 1)
        if action_type == "cancel":
            await self._set_paused(run_id, False)
            self.status = "Captura cancelada."
            await self.update(run_id, steps)
            return None
        if action_type == "clear":
            self._clear_steps(steps)
            await self._set_paused(run_id, False)
            self.status = "Mapa limpo."
            await self.update(run_id, steps)
            return len(steps)
        if action_type == "select":
            await self._set_paused(run_id, False)
            return self._select_step(steps, action)
        if action_type == "loop":
            marked = self._toggle_loop_point(steps, step)
            await self._set_paused(run_id, False)
            text = "marcado" if marked else "desmarcado"
            self.status = f"Ponto de loop {text}: {step.number} - {step.label}."
            await self.update(run_id, steps)
            return None
        if action_type in {"up", "down"}:
            override = await self._handle_reorder(run_id, steps, action, step, -1 if action_type == "up" else 1)
            await self._set_paused(run_id, False)
            return override
        if action_type == "create":
            step = await self._create_step(page, steps, action)
            await self._set_paused(run_id, False)
            self.current_step = step
            self.status = f"Ponto criado: {step.number} - {step.label}."
            await self.update(run_id, steps)
            return steps.index(step)
        if action_type == "remove":
            requested_number = self._requested_step_number(action)
            await self._handle_remove(steps, action, step)
            await self._set_paused(run_id, False)
            await self.update(run_id, steps)
            if requested_number is None or requested_number == step.number:
                return min(index, len(steps))
            return None
        if action_type == "capture":
            target = self._target_step(steps, action, step)
            await self._apply_capture(page, target, action)
            await self._set_paused(run_id, False)
            self.status = f"Ponto ajustado: {target.number} - {target.label} em {target.x},{target.y}."
            await self.update(run_id, steps)
        if action_type == "capture_scroll":
            target = self._target_step(steps, action, step)
            self._apply_scroll_capture(page, target, action)
            await self._set_paused(run_id, False)
            self.status = f"Rolagem ajustada: {target.number} - {target.label} em {target.scroll_x},{target.scroll_y}."
            await self.update(run_id, steps)
        if action_type == "capture_scroll_up":
            target = self._target_step(steps, action, step)
            self._apply_scroll_up_capture(page, target, action)
            await self._set_paused(run_id, False)
            self.status = (
                f"Rolagem (subir) ajustada: {target.number} - {target.label} "
                f"em {target.scroll_up_x},{target.scroll_up_y}."
            )
            await self.update(run_id, steps)
        if action_type == "edit":
            target = self._target_step(steps, action, step)
            self._apply_edit(page, target, action)
            await self._set_paused(run_id, False)
            self.status = f"Passo editado: {target.number} - {target.label}."
            await self.update(run_id, steps)
        if action_type == "reorder":
            self._apply_reorder(action)
            await self._set_paused(run_id, False)
            await self.update(run_id, steps)
        if action_type == "start_recording":
            await self.set_recording(page, run_id, True)
            self.status = "Gravando automaticamente: cada clique na tela vira um passo novo."
            await self.update(run_id, steps)
        if action_type == "stop_recording":
            await self.set_recording(page, run_id, False)
            self.status = "Gravação pausada."
            await self.update(run_id, steps)
        return None

    def _requested_step_number(self, action: dict[str, Any]) -> int | None:
        requested = action.get("step")
        if requested is None:
            return None
        try:
            return int(requested)
        except (TypeError, ValueError):
            return None

    def _target_step(
        self,
        steps: list[StepDefinition],
        action: dict[str, Any],
        fallback: StepDefinition,
    ) -> StepDefinition:
        # `steps` is frequently just a WINDOW of the full on-disk map (see the note on
        # _renumber_steps), so a step number the user picked in the UI may not be in this
        # particular slice even though it exists on disk (e.g. editing a step outside the
        # current loop range while a run is mid-loop). Fall back to loading it straight
        # from disk rather than silently acting on `fallback` (a different step).
        requested_number = self._requested_step_number(action)
        if requested_number is None:
            return fallback
        in_memory = next((item for item in steps if item.number == requested_number), None)
        if in_memory is not None:
            return in_memory
        return self._load_step_from_disk(requested_number) or fallback

    def _load_step_from_disk(self, number: int) -> StepDefinition | None:
        if not self.capture_file:
            return None
        for item in load_pointer_map_steps(self.capture_file):
            if item.number == number:
                return item
        return None

    async def _handle_reorder(
        self,
        run_id: str,
        steps: list[StepDefinition],
        action: dict[str, Any],
        executing_step: StepDefinition,
        delta: int,
    ) -> int | None:
        requested_number = self._requested_step_number(action)
        in_memory_target = (
            next((item for item in steps if item.number == requested_number), None)
            if requested_number is not None
            else None
        )
        if in_memory_target is not None or requested_number is None:
            target = in_memory_target or executing_step
            target_index = next(
                (idx for idx, item in enumerate(steps) if item.number == target.number),
                0,
            )
            moved = self._move_step(steps, target_index, target, delta)
            self.status = f"Passo reordenado: {target.number} - {target.label}."
            await self.update(run_id, steps)
            return moved if target.number == executing_step.number else None

        moved_info = self._move_step_on_disk(requested_number, delta)
        if moved_info:
            self.status = f"Passo reordenado: {moved_info[0]} - {moved_info[1]}."
        else:
            self.status = f"Não encontrei o passo {requested_number} no mapa pra reordenar."
        await self.update(run_id, steps)
        return None

    def _move_step_on_disk(self, number: int, delta: int) -> tuple[int, str] | None:
        ordered = self._read_ordered_points()
        if ordered is None:
            return None
        current = next((idx for idx, item in enumerate(ordered) if self._point_step(item) == number), None)
        if current is None:
            return None
        target_index = max(0, min(len(ordered) - 1, current + delta))
        return self._write_reordered_points(ordered, current, target_index)

    def _apply_reorder(self, action: dict[str, Any]) -> None:
        number = self._requested_step_number(action)
        to_number = self._optional_int(action.get("toStep"))
        if number is None or to_number is None:
            self.status = "Comando de arrastar sem passo de origem/destino."
            return
        moved_info = self._reorder_step_on_disk(number, to_number)
        self.status = (
            f"Passo reordenado: {moved_info[0]} - {moved_info[1]}."
            if moved_info
            else f"Não encontrei o passo {number} no mapa pra reordenar."
        )

    def _reorder_step_on_disk(self, number: int, to_number: int) -> tuple[int, str] | None:
        ordered = self._read_ordered_points()
        if ordered is None:
            return None
        current = next((idx for idx, item in enumerate(ordered) if self._point_step(item) == number), None)
        if current is None:
            return None
        target_index = next(
            (idx for idx, item in enumerate(ordered) if self._point_step(item) == to_number),
            current,
        )
        return self._write_reordered_points(ordered, current, target_index)

    def _read_ordered_points(self) -> list[dict[str, Any]] | None:
        if not self.capture_file:
            return None
        payload = read_json(self.capture_file, {})
        points = payload.get("points") if isinstance(payload, dict) else None
        if not isinstance(points, list):
            return None
        return sorted((item for item in points if isinstance(item, dict)), key=self._point_step)

    def _write_reordered_points(
        self,
        ordered: list[dict[str, Any]],
        current: int,
        target_index: int,
    ) -> tuple[int, str]:
        target_index = max(0, min(len(ordered) - 1, target_index))
        if current != target_index:
            ordered.insert(target_index, ordered.pop(current))
            for idx, item in enumerate(ordered, 1):
                item["step"] = idx
        payload = {
            "points": ordered,
            "totalPoints": len(ordered),
            "generatedAt": datetime.now(timezone.utc).isoformat(),
        }
        existing = read_json(self.capture_file, {}) if self.capture_file else {}
        if isinstance(existing, dict):
            payload = {**existing, **payload}
        write_json(self.capture_file, payload)
        moved_point = ordered[target_index]
        return moved_point["step"], str(moved_point.get("label") or "")

    def _optional_int(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _move_step(self, steps: list[StepDefinition], index: int, step: StepDefinition, delta: int) -> int:
        if not steps:
            return index
        current = next((idx for idx, item in enumerate(steps) if item.number == step.number), index)
        target = max(0, min(len(steps) - 1, current + delta))
        if current != target:
            steps.insert(target, steps.pop(current))
            self._renumber_steps(steps)
        self.current_index = target
        self.current_step = steps[target]
        return target

    def _toggle_loop_point(self, steps: list[StepDefinition], step: StepDefinition) -> bool:
        marked = not step.loop_point
        for item in steps:
            item.loop_point = False
        step.loop_point = marked
        if self.capture_file:
            payload = read_json(self.capture_file, {})
            points = payload.get("points") if isinstance(payload, dict) else None
            if isinstance(points, list):
                for point in [item for item in points if isinstance(item, dict)]:
                    point["loopPoint"] = self._point_step(point) == step.number and marked
                payload["generatedAt"] = datetime.now(timezone.utc).isoformat()
                write_json(self.capture_file, payload)
        return marked

    async def _control(self, run_id: str) -> dict[str, Any]:
        return {"action": pop_overlay_command(run_id), "paused": peek_overlay_paused(run_id)}

    async def is_paused(self, run_id: str) -> bool:
        """Non-consuming peek at the paused flag (does not clear any pending command)."""
        if not self.enabled:
            return False
        return peek_overlay_paused(run_id)

    async def _set_paused(self, run_id: str, paused: bool) -> None:
        set_overlay_paused(run_id, paused)

    async def _ensure_recording_listener(self, page: Page, run_id: str) -> None:
        if self._recording_bound:
            return
        async def _on_click(x: float, y: float) -> None:
            push_recorded_click(run_id, int(x), int(y))

        try:
            await page.expose_function("__rodoparReportClick", _on_click)
        except Exception:
            pass
        try:
            await page.evaluate(_RECORDING_SCRIPT)
        except Exception:
            pass
        self._recording_bound = True

    async def set_recording(self, page: Page, run_id: str, active: bool) -> None:
        await self._ensure_recording_listener(page, run_id)
        try:
            await page.evaluate("active => { window.__rodoparRecordingActive = active; }", active)
        except Exception:
            pass
        self.recording = active

    async def _drain_recorded_clicks(self, page: Page, run_id: str, steps: list[StepDefinition]) -> None:
        for x, y in pop_recorded_clicks(run_id):
            step = await self._create_step(page, steps, {"x": x, "y": y})
            self.current_step = step
            self.status = f"Ponto gravado automaticamente: {step.number} - {step.label} em {x},{y}."
            await self.update(run_id, steps)

    async def _apply_capture(self, page: Page, step: StepDefinition, action: dict[str, Any]) -> None:
        x = max(0, int(float(action.get("x") or 0)))
        y = max(0, int(float(action.get("y") or 0)))
        step.x = x
        step.y = y
        template = await self._capture_template(page, x, y)
        if template:
            step.template = template
        self._persist_step(page, step, action)

    def _apply_scroll_capture(self, page: Page, step: StepDefinition, action: dict[str, Any]) -> None:
        step.scroll_x = max(0, int(float(action.get("x") or 0)))
        step.scroll_y = max(0, int(float(action.get("y") or 0)))
        self._persist_step(page, step, action)

    def _apply_scroll_up_capture(self, page: Page, step: StepDefinition, action: dict[str, Any]) -> None:
        step.scroll_up_x = max(0, int(float(action.get("x") or 0)))
        step.scroll_up_y = max(0, int(float(action.get("y") or 0)))
        self._persist_step(page, step, action)

    def _apply_edit(self, page: Page, step: StepDefinition, action: dict[str, Any]) -> None:
        label = str(action.get("label") or step.label).strip() or step.label
        shortcut = str(action.get("shortcut") or "").strip()
        ocr_text = str(action.get("ocrText") or "").strip()
        if "delayMs" in action:
            step.delay_ms = self._parse_delay_ms(action.get("delayMs"))
        if "manualPause" in action:
            step.requires_manual = bool(action.get("manualPause"))
        if "reliableClick" in action:
            step.reliable_click = bool(action.get("reliableClick")) or None

        step.label = label
        step.shortcut = shortcut or None
        step.ocr_text = ocr_text or None
        if shortcut:
            step.action = "shortcut"
            step.input_key = None
        elif ocr_text:
            step.action = "ocr_click"
            step.input_key = None
        else:
            step.action, step.input_key = action_for_label(label)
        self._persist_step(page, step, action)

    async def _create_step(
        self,
        page: Page,
        steps: list[StepDefinition],
        action: dict[str, Any],
    ) -> StepDefinition:
        number = self._next_step_number(steps)
        label = str(action.get("label") or f"PASSO-{number}").strip() or f"PASSO-{number}"
        delay_ms = self._parse_delay_ms(action.get("delayMs"))
        shortcut = str(action.get("shortcut") or "").strip()

        if shortcut:
            step = StepDefinition(
                number=number,
                label=label,
                action="shortcut",
                x=0,
                y=0,
                viewport=Viewport(
                    width=self.settings.browser_width,
                    height=self.settings.browser_height,
                    dpr=1,
                ),
                shortcut=shortcut,
                enabled=True,
                delay_ms=delay_ms,
            )
            steps.append(step)
            self._persist_step(page, step, action)
            return step

        ocr_text = str(action.get("ocrText") or "").strip()
        x = max(0, int(float(action.get("x") or 0)))
        y = max(0, int(float(action.get("y") or 0)))

        if ocr_text:
            step = StepDefinition(
                number=number,
                label=label,
                action="ocr_click",
                x=x,
                y=y,
                viewport=Viewport(
                    width=self.settings.browser_width,
                    height=self.settings.browser_height,
                    dpr=1,
                ),
                ocr_text=ocr_text,
                enabled=True,
                delay_ms=delay_ms,
            )
            steps.append(step)
            self._persist_step(page, step, action)
            return step

        step_action, input_key = action_for_label(label)
        step = StepDefinition(
            number=number,
            label=label,
            action=step_action,
            x=x,
            y=y,
            viewport=Viewport(
                width=self.settings.browser_width,
                height=self.settings.browser_height,
                dpr=1,
            ),
            template=await self._capture_template(page, x, y),
            input_key=input_key,
            enabled=True,
            delay_ms=delay_ms,
        )
        steps.append(step)
        self._persist_step(page, step, action)
        return step

    def _parse_delay_ms(self, value: Any) -> int | None:
        try:
            parsed = int(float(str(value).strip()))
        except (TypeError, ValueError, AttributeError):
            return None
        return parsed if parsed > 0 else None

    async def _capture_template(self, page: Page, x: int, y: int) -> StepTemplate | None:
        if not self.capture_file:
            return None
        left = max(0, min(self.settings.browser_width - TEMPLATE_WIDTH, x - TEMPLATE_WIDTH // 2))
        top = max(0, min(self.settings.browser_height - TEMPLATE_HEIGHT, y - TEMPLATE_HEIGHT // 2))
        width = min(TEMPLATE_WIDTH, self.settings.browser_width - left)
        height = min(TEMPLATE_HEIGHT, self.settings.browser_height - top)
        if width <= 0 or height <= 0:
            return None
        await set_overlay_visible(page, False)
        await page.wait_for_timeout(30)
        try:
            image = await page.screenshot(
                type="png",
                clip={"x": left, "y": top, "width": width, "height": height},
            )
        except Exception:
            return None
        finally:
            await set_overlay_visible(page, True)
        templates_dir = self.capture_file.parent / "templates"
        templates_dir.mkdir(parents=True, exist_ok=True)
        file_path = templates_dir / f"step-{uuid4().hex}.png"
        file_path.write_bytes(image)
        return StepTemplate(path=self._relative_path(file_path), width=width, height=height)

    def _relative_path(self, path: Path) -> str:
        root = self.settings.backend_root.parent
        try:
            return str(path.relative_to(root))
        except ValueError:
            return str(path)

    def _select_step(self, steps: list[StepDefinition], action: dict[str, Any]) -> int | None:
        target = self._point_step({"step": action.get("step")})
        for index, step in enumerate(steps):
            if step.number == target:
                self.current_index = index
                self.current_step = step
                self.status = f"Passo selecionado: {step.number} - {step.label}."
                return index
        return None

    def _persist_step(self, page: Page, step: StepDefinition, action: dict[str, Any]) -> None:
        if not self.capture_file:
            return
        payload = read_json(self.capture_file, {})
        points = payload.get("points") if isinstance(payload, dict) else None
        if not isinstance(points, list):
            points = []
            payload = {"source": "pre-passo", "points": points}
        now = datetime.now(timezone.utc).isoformat()
        target = next((item for item in points if int(item.get("step") or 0) == step.number), None)
        if target is None:
            target = {"step": step.number, "label": step.label}
            points.append(target)
        target.update(
            {
                "label": step.label,
                "x": step.x,
                "y": step.y,
                "screenX": int(float(action.get("screenX") or step.x)),
                "screenY": int(float(action.get("screenY") or step.y)),
                "url": self._safe_url(page),
                "capturedAt": now,
                "viewport": step.viewport.model_dump(mode="json"),
                "loopPoint": step.loop_point,
                "template": step.template.model_dump(mode="json") if step.template else None,
                "shortcut": step.shortcut,
                "ocrText": step.ocr_text,
                "scrollX": step.scroll_x,
                "scrollY": step.scroll_y,
                "scrollUpX": step.scroll_up_x,
                "scrollUpY": step.scroll_up_y,
                "delayMs": step.delay_ms,
                "manualPause": step.requires_manual,
                "reliableClick": step.reliable_click,
            }
        )
        points.sort(key=lambda item: int(item.get("step") or 0))
        payload["totalPoints"] = len(points)
        payload["generatedAt"] = now
        write_json(self.capture_file, payload)

    def _clear_steps(self, steps: list[StepDefinition]) -> None:
        steps.clear()
        self.current_index = -1
        self.current_step = None
        if not self.capture_file:
            return
        now = datetime.now(timezone.utc).isoformat()
        write_json(
            self.capture_file,
            {
                "source": "rodopar-pdf-overlay",
                "generatedAt": now,
                "totalPoints": 0,
                "captureViewport": {
                    "width": self.settings.browser_width,
                    "height": self.settings.browser_height,
                    "dpr": 1,
                },
                "points": [],
            },
        )

    async def _handle_remove(
        self,
        steps: list[StepDefinition],
        action: dict[str, Any],
        fallback: StepDefinition,
    ) -> None:
        number = self._requested_step_number(action) or fallback.number
        in_memory_index = next((idx for idx, item in enumerate(steps) if item.number == number), None)
        if in_memory_index is not None:
            steps.pop(in_memory_index)
        label = self._remove_step_on_disk(number)
        if label is None and in_memory_index is not None:
            label = fallback.label if number == fallback.number else ""
        if label is not None:
            self.status = f"Passo removido: {number} - {label}."
        else:
            self.status = f"Não encontrei o passo {number} no mapa pra remover."

    def _remove_step_on_disk(self, number: int) -> str | None:
        ordered = self._read_ordered_points()
        if ordered is None:
            return None
        target = next((item for item in ordered if self._point_step(item) == number), None)
        if target is None:
            return None
        label = str(target.get("label") or "")
        remaining = [item for item in ordered if item is not target]
        for idx, item in enumerate(remaining, 1):
            item["step"] = idx
        payload = {
            "points": remaining,
            "totalPoints": len(remaining),
            "generatedAt": datetime.now(timezone.utc).isoformat(),
        }
        existing = read_json(self.capture_file, {}) if self.capture_file else {}
        if isinstance(existing, dict):
            payload = {**existing, **payload}
        write_json(self.capture_file, payload)
        return label
        self._renumber_steps(steps)

    def _renumber_steps(self, steps: list[StepDefinition]) -> None:
        # `steps` is often only a WINDOW of the full map (e.g. a live-replay loop range,
        # or the enabled-only subset used by post-replay editing) — never a guaranteed
        # full copy of what's on disk. This must merge, not replace: any on-disk point
        # outside that window has to survive untouched, in its original relative position.
        old_numbers = [step.number for step in steps]
        if not self.capture_file:
            for number, step in enumerate(steps, 1):
                step.number = number
            return

        payload = read_json(self.capture_file, {})
        points = payload.get("points") if isinstance(payload, dict) else None
        if not isinstance(points, list):
            for number, step in enumerate(steps, 1):
                step.number = number
            return

        disk_points = sorted(
            (item for item in points if isinstance(item, dict)),
            key=self._point_step,
        )
        known_old = set(old_numbers)
        by_old_number = {self._point_step(item): item for item in disk_points}
        subset_order = [by_old_number[old] for old in old_numbers if old in by_old_number]

        merged: list[dict[str, Any]] = []
        subset_inserted = False
        for item in disk_points:
            if self._point_step(item) in known_old:
                if not subset_inserted:
                    merged.extend(subset_order)
                    subset_inserted = True
                continue
            merged.append(item)
        if not subset_inserted:
            merged.extend(subset_order)

        for number, item in enumerate(merged, 1):
            item["step"] = number
        for step, old in zip(steps, old_numbers):
            match = by_old_number.get(old)
            if match is not None:
                step.number = match["step"]

        payload["points"] = merged
        payload["totalPoints"] = len(merged)
        payload["generatedAt"] = datetime.now(timezone.utc).isoformat()
        write_json(self.capture_file, payload)

    def _next_step_number(self, steps: list[StepDefinition]) -> int:
        if self.capture_file:
            payload = read_json(self.capture_file, {})
            points = payload.get("points") if isinstance(payload, dict) else None
            if isinstance(points, list):
                existing = [self._point_step(item) for item in points if isinstance(item, dict)]
                if existing:
                    return max(existing) + 1
        return len(steps) + 1

    def _point_step(self, item: Any) -> int:
        try:
            return int(item.get("step") or 0) if isinstance(item, dict) else 0
        except (TypeError, ValueError):
            return 0

    def _payload(self, steps: list[StepDefinition]) -> dict[str, Any]:
        current = self.current_step
        return {
            "status": self.status,
            "captureFile": str(self.capture_file),
            "currentStep": current.number if current else None,
            "currentLabel": current.label if current else "",
            "recording": self.recording,
            "points": [
                {
                    "step": step.number,
                    "label": step.label,
                    "x": step.x,
                    "y": step.y,
                    "loopPoint": step.loop_point,
                    "hasTemplate": bool(step.template and step.template.path),
                    "shortcut": step.shortcut or "",
                    "ocrText": step.ocr_text or "",
                    "hasScrollTarget": step.scroll_x is not None and step.scroll_y is not None,
                    "hasScrollUpTarget": step.scroll_up_x is not None and step.scroll_up_y is not None,
                    "delayMs": step.delay_ms,
                    "requiresManual": step.requires_manual,
                    "reliableClick": step.reliable_click,
                }
                for step in steps
            ],
        }

    def _resolve(self, value: str) -> Path | None:
        if not value: return None
        path = Path(value)
        return path if path.is_absolute() else self.settings.backend_root.parent / path

    def _safe_url(self, page: Page) -> str:
        try:
            return page.url
        except Exception:
            return ""
