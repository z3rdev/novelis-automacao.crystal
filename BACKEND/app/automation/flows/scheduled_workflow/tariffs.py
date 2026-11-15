"""Await the existing HTTP tariff importer before advancing the workflow."""

from app.automation.flows.flow_events import emit_step
from app.services.tariffs.errors import TariffRefreshError
from app.services.tariffs.service import TariffService


async def refresh_tariffs(config, emit, run_id):
    service = TariffService(config)
    try:
        await emit_step(
            emit, run_id, "tariffs.refresh_started", "Tarifário Novelis: consultando o portal."
        )
        try:
            status = await service.refresh_and_wait()
        except TariffRefreshError as exc:
            await emit(
                str(exc), run_id=run_id, kind="tariffs.refresh_failed", level="error",
                payload={"stage": exc.stage, "error_code": exc.code},
            )
            raise
        except TimeoutError:
            raise RuntimeError(
                "A atualização do tarifário excedeu o tempo de espera. "
                "Confira a sincronização em Tarifas e tonelagem."
            ) from None
        await emit_step(
            emit,
            run_id,
            "tariffs.refreshed",
            f"Tarifário Novelis: catálogo atualizado com {status['total']} tarifas.",
            {"total": status["total"], "completed_at": status.get("completed_at")},
        )
        return status
    finally:
        # Only this node's collection is cancelled. Other computers retain their lease.
        await service.close()
