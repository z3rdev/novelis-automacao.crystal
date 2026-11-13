from collections.abc import Awaitable, Callable
from typing import Any

from app.automation.cancellation import check_cancelled

Emit = Callable[..., Awaitable[object]]


async def emit_step(
    emit: Emit,
    run_id: str,
    kind: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> None:
    check_cancelled()
    await emit(message, run_id=run_id, kind=kind, payload=payload or {})


async def emit_warn(
    emit: Emit,
    run_id: str,
    kind: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> None:
    check_cancelled()
    await emit(message, run_id=run_id, level="warn", kind=kind, payload=payload or {})
