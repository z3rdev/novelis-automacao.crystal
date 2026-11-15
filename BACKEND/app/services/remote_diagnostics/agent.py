"""Every updated operator backend can answer developer-queued read requests."""

import asyncio
import logging
from contextlib import suppress

from app.domain.remote_diagnostics import DiagnosticOptions
from app.infrastructure.chamados_postgres import CommunicationUnavailable
from app.services.remote_diagnostics.process import ProbeRunner
from app.services.remote_diagnostics.redaction import Redactor

logger = logging.getLogger(__name__)


class DiagnosticAgent:
    def __init__(self, settings, config, presence, queue, runner=None):
        self.config, self.presence, self.queue = config, presence, queue
        self.runner = runner or ProbeRunner(settings)
        self.task, self.job, self.current = None, None, None
        self.last_error = False

    async def execute(self, request):
        try:
            options = DiagnosticOptions.model_validate(request["options"])
            result = await self.runner.collect(options)
            # A second redaction pass includes any current machine-specific secrets.
            result = Redactor(self.config).clean(result)
            await asyncio.to_thread(
                self.queue.finish, request["id"], self.presence.instance_id, result
            )
        except asyncio.CancelledError:
            with suppress(CommunicationUnavailable):
                await asyncio.shield(
                    asyncio.to_thread(
                        self.queue.finish,
                        request["id"],
                        self.presence.instance_id,
                        error="agent_stopped",
                    )
                )
            raise
        except Exception:  # noqa: BLE001 - isolate vendor/probe failures and never return raw exceptions.
            # No exception from SDK/libpq/probe is printed or returned to the developer.
            with suppress(CommunicationUnavailable):
                await asyncio.to_thread(
                    self.queue.finish,
                    request["id"],
                    self.presence.instance_id,
                    error="probe_unavailable",
                )
        finally:
            self.current = None

    async def tick(self):
        device = self.presence.device({"status": "idle"})
        await asyncio.to_thread(
            self.queue.heartbeat, device, self.presence.instance_id, self.current
        )
        if self.job is None or self.job.done():
            if self.job:
                await self.job
            request = await asyncio.to_thread(
                self.queue.claim, device["id"], self.presence.instance_id
            )
            if request:
                self.current = request["id"]
                self.job = asyncio.create_task(self.execute(request))

    async def loop(self):
        while True:
            try:
                await self.tick()
                self.last_error = False
            except (CommunicationUnavailable, OSError, ValueError):
                if not self.last_error:
                    logger.warning("Diagnóstico remoto aguardando o banco de comunicação.")
                self.last_error = True
            await asyncio.sleep(15)

    def start(self):
        if self.queue.enabled and self.config.bool("DIAGNOSTICS_AGENT_ENABLED", True):
            self.task = asyncio.create_task(self.loop())

    async def close(self):
        for task in (self.task, self.job):
            if task and not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
        if self.task:
            with suppress(CommunicationUnavailable, OSError):
                await asyncio.to_thread(
                    self.queue.leave,
                    self.presence.device({"status": "idle"})["id"],
                    self.presence.instance_id,
                )
