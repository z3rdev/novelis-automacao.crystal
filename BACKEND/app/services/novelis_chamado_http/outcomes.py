"""Persist sanitized results and publish the existing report-compatible events."""

import json
from datetime import UTC, datetime

from app.automation.flows.flow_events import emit_step, emit_warn

from . import ChamadoHttpError


def record(path, value):
    value = {"checked_at": datetime.now(UTC).isoformat(), "browser_started": False, **value}
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


async def publish_result(emit, run_id, result):
    if result["status"] in {"already_exists", "duplicate"}:
        await emit_warn(
            emit,
            run_id,
            "novelis.chamado_exists",
            f"CT-e já possui chamado {result.get('number') or ''}.",
            result,
        )
    elif result["status"] == "confirmed":
        await emit_step(
            emit,
            run_id,
            "novelis.save",
            f"Chamado {result['number']} confirmado por HTTP.",
            {**result, "result": {"ok": True}, "numeroChamado": result["number"]},
        )
        if not result.get("attachments_visible"):
            await emit_warn(
                emit,
                run_id,
                "novelis.http.attachments_unverified",
                "Chamado criado. A leitura dos anexos precisa ser conferida no portal.",
            )
        if not result.get("catalog_updated"):
            await emit_warn(
                emit,
                run_id,
                "novelis.http.catalog_pending",
                "Chamado criado. A atualização do catálogo compartilhado está pendente.",
            )
    elif result["status"] == "indeterminate":
        await emit_warn(
            emit,
            run_id,
            "novelis.http.indeterminate",
            "Envio HTTP com confirmação pendente. Confira no portal antes de repetir.",
            result,
        )
        raise ChamadoHttpError(
            "O portal ainda não confirmou a abertura HTTP. O envio foi registrado para conferência."
        )
    else:
        await emit_step(emit, run_id, "novelis.http.prepared", "Chamado HTTP preparado.", result)
    return result
