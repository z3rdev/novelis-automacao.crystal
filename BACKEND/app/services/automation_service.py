import asyncio
import logging

from app.automation.cancellation import RunCancellation, cancellation_scope, check_cancelled
from app.automation.flows.legacy_coordinator import LegacyCoordinator
from app.config.legacy_config import LegacyConfig
from app.config.settings import Settings
from app.domain.models import RunSnapshot, RunStartRequest
from app.domain.run_state import RunState
from app.domain.automation_errors import AutomationBusyError
from app.infrastructure.event_bus import EventBus
from app.services.browser_driver import BrowserDriver
from app.services.capture_cleanup import clean_capture_roots
from app.services.rodopar_policy import LEGACY_RODOPAR_FLOWS, require_legacy_rodopar
from app.services.step_repository import StepRepository

logger = logging.getLogger(__name__)

class AutomationService:
    STOP_WAIT_SECONDS = 3

    def __init__(
        self,
        settings: Settings,
        legacy_config: LegacyConfig,
        repository: StepRepository,
        event_bus: EventBus,
        run_state: RunState,
        browser: BrowserDriver,
        run_reports=None,
    ) -> None:
        self.settings = settings
        self.legacy_config = legacy_config
        self.repository = repository
        self.event_bus = event_bus
        self.run_state = run_state
        self.browser = browser
        self.run_reports = run_reports
        self._control_lock = asyncio.Lock()
        self._cancellation: RunCancellation | None = None
        self._task: asyncio.Task[None] | None = None

    async def current(self) -> RunSnapshot:
        return await self.run_state.get()

    async def start(self, request: RunStartRequest) -> RunSnapshot:
        if request.flow.strip().lower() in LEGACY_RODOPAR_FLOWS:
            require_legacy_rodopar(self.legacy_config)
        async with self._control_lock:
            if self._task and not self._task.done():
                raise AutomationBusyError("A execucao anterior ainda esta encerrando. Aguarde a parada concluir.")
            snapshot = await self.run_state.start(request.flow, request.dry_run)
            self._cancellation = RunCancellation()
            self._task = asyncio.create_task(self._execute(request, snapshot.id, self._cancellation))
            return snapshot

    async def stop(self) -> RunSnapshot:
        async with self._control_lock:
            task = self._task
            if not task or task.done():
                return await self.run_state.get()
            if (await self.run_state.get()).status not in {"running", "stopping"}:
                return await self.run_state.get()
            cancellation = self._cancellation
            if cancellation and not cancellation.cancelled.is_set():
                cancellation.request_cancel()
                task.cancel()
                snapshot = await self.run_state.request_stop()
                await self.event_bus.publish("Parada solicitada pelo usuário.", run_id=snapshot.id,
                                             level="warn", kind="run.stop_requested")
            else:
                snapshot = await self.run_state.get()
        if task and not task.done():
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=self.STOP_WAIT_SECONDS)
            except (asyncio.CancelledError, TimeoutError):
                pass
        if task.cancelled():
            async with self._control_lock:
                if self._task is task:
                    await self.run_state.update(status="cancelled", message="Execução cancelada.")
                    await self.event_bus.publish("Execução cancelada.", run_id=snapshot.id,
                                                 level="warn", kind="run.cancelled")
                    self._task = None
        return await self.run_state.get()

    async def _execute(self, request: RunStartRequest, run_id: str, cancellation: RunCancellation) -> None:
        with cancellation_scope(cancellation):
            await self._run(request, run_id, cancellation)

    async def _run(self, request: RunStartRequest, run_id: str, cancellation: RunCancellation) -> None:
        browser: BrowserDriver | None = None
        completed_successfully = False
        cancelled = False
        flow_name = request.flow.strip().lower()
        consulta_headless = flow_name in {"consulta-pendentes", "consulta"} and self.settings.consulta_browser_headless
        try:
            await self.event_bus.publish(
                "Execução iniciada.",
                run_id=run_id,
                kind="run.started",
                payload=self._run_started_payload(request),
            )
            if self.run_reports:
                try:
                    await self.run_reports.begin(await self.run_state.get(), request)
                except Exception:  # noqa: BLE001 - reporting must not interrupt the fiscal workflow.
                    await self.event_bus.publish("Registro do relatório da execução indisponível.",
                        run_id=run_id, level="warn", kind="execution_report.pending")
            if flow_name != "chamado-http" and (not request.dry_run or flow_name == "pendentes"):
                browser = BrowserDriver(self.settings, headless_override=True) if consulta_headless else self.browser
                if consulta_headless:
                    await self.event_bus.publish(
                        "Consulta rodando sem exibir navegador.",
                        run_id=run_id,
                        kind="consulta.headless",
                    )

            coordinator = LegacyCoordinator(
                self.settings,
                self.legacy_config,
                self.repository,
                self.event_bus,
            )
            result = await coordinator.run(request, run_id, browser)
            if flow_name == "pendentes" and isinstance(result, dict) and result.get("errors"):
                errors = result.get("errors") or []
                raise RuntimeError(f"Iniciar automação finalizado com {len(errors)} erro(s).")

            check_cancelled()
            await self.run_state.update(status="completed", message="Execução concluída.")
            await self.event_bus.publish("Execução concluída.", run_id=run_id, kind="run.completed")
            completed_successfully = True
        except asyncio.CancelledError:
            cancelled = True
        except Exception as exc:
            logger.debug("Fluxo encerrado por excecao.", exc_info=True)
            if cancellation.cancelled.is_set():
                cancelled = True
            else:
                await self.run_state.update(status="failed", message=str(exc))
                await self.event_bus.publish(f"Falha na execução: {exc}", run_id=run_id,
                                             level="error", kind="run.failed")
        finally:
            if cancelled:
                cancellation.request_cancel()
                await cancellation.drain()
            if browser and (cancelled or flow_name in {"pendentes", "consulta-pendentes", "consulta", "buscar-chamados", "workflow"}):
                try:
                    await browser.close()
                    await self.event_bus.publish("Navegador da automação fechado.", run_id=run_id, kind="browser.closed")
                except Exception:
                    logger.debug("Navegador ja encerrado durante a limpeza.", exc_info=True)
            if completed_successfully and flow_name == "pendentes":
                cleanup = clean_capture_roots(self.settings.backend_root.parent, self.settings.backend_root)
                cleanup_errors = cleanup.get("errors") or []
                await self.event_bus.publish(
                    "Captures limpos após finalização da automação com sucesso.",
                    run_id=run_id,
                    level="warn" if cleanup_errors else "info",
                    kind="captures.cleaned",
                    payload=cleanup,
                )
            if cancelled:
                await self.run_state.update(status="cancelled", message="Execução cancelada.")
                await self.event_bus.publish("Execução cancelada.", run_id=run_id,
                                             level="warn", kind="run.cancelled")
            if flow_name == "workflow" and request.workflow:
                from app.services.workflow_finalization import finalize_workflow
                await finalize_workflow(request, await self.run_state.get(), self.event_bus, self.run_reports)
            elif self.run_reports:
                try:
                    report = await self.run_reports.finish(await self.run_state.get())
                    if report:
                        await self.event_bus.publish("Relatório de chamados da execução gerado.", run_id=run_id,
                            kind="execution_report.created", payload={"report_id": report["id"],
                            "opened_count": report["opened_count"], "status": report["status"]})
                except Exception:  # noqa: BLE001 - redact storage errors; fiscal results stay unchanged.
                    await self.event_bus.publish("Não foi possível finalizar o relatório. Os eventos da execução foram preservados.",
                        run_id=run_id, level="warn", kind="execution_report.pending")
            if self._task is asyncio.current_task():
                self._task = None

    def _run_started_payload(self, request: RunStartRequest) -> dict[str, object]:
        payload = request.model_dump(mode="json")
        manual_ctes = str(payload.get("manual_ctes") or "")
        if len(manual_ctes) > 200:
            payload["manual_ctes"] = f"{manual_ctes[:200]}... ({len(manual_ctes)} caracteres)"
        spreadsheet = payload.get("manual_spreadsheet")
        if isinstance(spreadsheet, dict):
            payload["manual_spreadsheet"] = {
                "filename": spreadsheet.get("filename", ""),
                "content_base64": "<omitido>",
            }
        return payload
