import threading
from typing import Any


_LOCK = threading.Lock()
_STATES: dict[str, dict[str, Any]] = {}
_COMMANDS: dict[str, dict[str, Any]] = {}
_PAUSED: dict[str, bool] = {}
_RECORDED_CLICKS: dict[str, list[tuple[int, int]]] = {}


def set_overlay_state(run_id: str, payload: dict[str, Any]) -> None:
    with _LOCK:
        _STATES[run_id] = payload


def get_overlay_state(run_id: str) -> dict[str, Any] | None:
    with _LOCK:
        state = _STATES.get(run_id)
        return dict(state) if state is not None else None


def push_overlay_command(run_id: str, command: dict[str, Any]) -> None:
    with _LOCK:
        _COMMANDS[run_id] = command


def pop_overlay_command(run_id: str) -> dict[str, Any] | None:
    with _LOCK:
        return _COMMANDS.pop(run_id, None)


def peek_overlay_paused(run_id: str) -> bool:
    """Non-consuming peek at the paused flag (does not clear any pending command)."""
    with _LOCK:
        return bool(_PAUSED.get(run_id, False))


def set_overlay_paused(run_id: str, paused: bool) -> None:
    with _LOCK:
        _PAUSED[run_id] = paused


def push_recorded_click(run_id: str, x: int, y: int) -> None:
    """Queued separately from push_overlay_command: real clicks made while recording can
    arrive faster than the ~0.45s poll loop drains the single command slot, so a list here
    avoids silently losing any of them."""
    with _LOCK:
        _RECORDED_CLICKS.setdefault(run_id, []).append((x, y))


def pop_recorded_clicks(run_id: str) -> list[tuple[int, int]]:
    with _LOCK:
        clicks = _RECORDED_CLICKS.get(run_id)
        if not clicks:
            return []
        _RECORDED_CLICKS[run_id] = []
        return clicks
