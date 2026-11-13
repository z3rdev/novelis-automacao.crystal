import re
from pathlib import Path
from typing import Any

from app.domain.models import StepDefinition, StepTemplate, Viewport
from app.infrastructure.json_store import read_json


def load_pointer_map_steps(path: Path) -> list[StepDefinition]:
    payload = read_json(path, {})
    points = payload.get("points") if isinstance(payload, dict) else None
    if not isinstance(points, list):
        return []

    steps: list[StepDefinition] = []
    for point in sorted(points, key=_point_order):
        if not isinstance(point, dict):
            continue
        step_number = _positive_int(point.get("step"))
        if not step_number:
            continue
        label = str(point.get("label") or f"STEP_{step_number}").strip()
        x = _positive_int(point.get("x"), allow_zero=True)
        y = _positive_int(point.get("y"), allow_zero=True)
        if x is None or y is None:
            continue
        shortcut = str(point.get("shortcut") or "").strip() or None
        ocr_text = str(point.get("ocrText") or "").strip() or None
        if shortcut:
            action, input_key = "shortcut", None
        elif ocr_text:
            action, input_key = "ocr_click", None
        else:
            action, input_key = _action_for_label(label)
        steps.append(
            StepDefinition(
                number=step_number,
                label=label,
                action=action,
                x=x,
                y=y,
                viewport=_viewport(point),
                template=_template(point.get("template")),
                shortcut=shortcut,
                ocr_text=ocr_text,
                scroll_x=_positive_int(point.get("scrollX"), allow_zero=True),
                scroll_y=_positive_int(point.get("scrollY"), allow_zero=True),
                scroll_up_x=_positive_int(point.get("scrollUpX"), allow_zero=True),
                scroll_up_y=_positive_int(point.get("scrollUpY"), allow_zero=True),
                input_key=input_key,
                enabled=True,
                delay_ms=_positive_int(point.get("delayMs"), allow_zero=True),
                loop_point=_is_loop_point(point, label),
                reliable_click=point.get("reliableClick") if isinstance(point.get("reliableClick"), bool) else None,
                requires_manual=bool(point.get("manualPause")),
            )
        )
    return steps


def find_step_number(steps: list[StepDefinition], pattern: str) -> int | None:
    regex = re.compile(pattern, re.I)
    for step in steps:
        if regex.search(step.label):
            return step.number
    return None


def action_for_label(label: str) -> tuple[str, str | None]:
    return _action_for_label(label)


def _point_order(point: Any) -> int:
    if not isinstance(point, dict):
        return 0
    return _positive_int(point.get("step")) or 0


def _action_for_label(label: str) -> tuple[str, str | None]:
    normalized = re.sub(r"[^A-Z0-9]+", "", label.upper())
    if "INPUTCTRCINICIAL" in normalized or "INPUTCRTCINICIAL" in normalized:
        return "fill", "documento"
    if "INPUTCTRCFINAL" in normalized or "INPUTCRTCFINAL" in normalized:
        return "fill", "documento"
    if "INPUTFILIALCTRC" in normalized or "INPUTFILIALCRTC" in normalized:
        return "fill", "filial"
    if "INPUTSERIECTRC" in normalized or "INPUTSERIECRTC" in normalized:
        return "fill", "serie"
    if "INPUTTEXTNOMECTRC" in normalized or "INPUTTEXTNOMECRTC" in normalized:
        return "fill", "nome_arquivo"
    if "INPUTNOMECTRC" in normalized or "INPUTNOMECRTC" in normalized:
        return "fill", "nome_arquivo"
    if "INPUT" in normalized:
        return "fill", None
    return "click", None


def _is_loop_point(point: dict[str, Any], label: str) -> bool:
    if "loopPoint" in point:
        return bool(point.get("loopPoint"))
    if "loop_point" in point:
        return bool(point.get("loop_point"))
    return re.sub(r"[^A-Z0-9]+", "_", label.upper()).strip("_") == "INICIO_LOOP"


def _viewport(point: dict[str, Any]) -> Viewport:
    raw = point.get("viewport") if isinstance(point.get("viewport"), dict) else {}
    return Viewport(
        width=_positive_int(raw.get("width")) or 1024,
        height=_positive_int(raw.get("height")) or 750,
        dpr=float(raw.get("dpr") or 1),
    )


def _template(raw: Any) -> StepTemplate | None:
    if not isinstance(raw, dict):
        return None
    path = str(raw.get("path") or "").strip()
    if not path:
        return None
    return StepTemplate(
        path=path,
        width=_positive_int(raw.get("width")) or 160,
        height=_positive_int(raw.get("height")) or 70,
    )


def _positive_int(value: Any, allow_zero: bool = False) -> int | None:
    try:
        parsed = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None
    if parsed > 0 or (allow_zero and parsed == 0):
        return parsed
    return None
