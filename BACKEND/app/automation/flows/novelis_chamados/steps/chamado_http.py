"""App run lifecycle and execution-report events for a single HTTP opening test."""

from datetime import UTC, datetime
from uuid import uuid4

import httpx

from app.automation.flows.flow_events import emit_step
from app.services.novelis_chamado_http import ChamadoHttpError
from app.services.novelis_chamado_http.outcomes import publish_result
from app.services.novelis_chamado_http.runner import run_ticket_test
from app.services.novelis_report_http import ReportDownloadError


async def run_http_test(settings, config, request, run_id, emit):
    output = (
        settings.backend_root.parent
        / "runtime/chamado-http-tests"
        / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"
    )
    output.mkdir(parents=True, exist_ok=True)

    async def notify(kind, message, payload):
        await emit_step(emit, run_id, kind, message, payload)

    try:
        result = await run_ticket_test(
            settings, config, request.sample_cte, output, send=not request.dry_run, notify=notify
        )
    except (httpx.HTTPError, ReportDownloadError):
        raise ChamadoHttpError(
            "A comunicação HTTP com o portal falhou. Confira o resultado registrado antes de repetir."
        ) from None
    return await publish_result(emit, run_id, result)
