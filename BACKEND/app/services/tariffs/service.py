"""Read a centralized catalog and refresh at the validity boundary, once per fleet."""

import asyncio
import logging
from datetime import datetime
from threading import Lock

from app.infrastructure.chamados_postgres import CommunicationUnavailable
from app.infrastructure.tariffs_postgres import TariffsPostgres

from .errors import TariffRefreshError, failure_code, failure_message
from .models import ZONE, estimate, next_check, project
from .municipalities import normalized, portal_cities
from .portal import PortalError, collect

logger = logging.getLogger(__name__)


class TariffService:
    def __init__(self, config, repository=None, collector=collect, clock=None):
        self.config = config
        self.repository = repository or TariffsPostgres(config)
        self.collector = collector
        self.clock = clock or (lambda: datetime.now(ZONE))
        self._ready, self._lock = False, Lock()
        self._loop_task, self._job = None, None

    def ensure(self):
        if not self.repository.enabled:
            raise CommunicationUnavailable(
                "Configure o PostgreSQL de comunicação para o catálogo de tarifas."
            )
        with self._lock:
            if not self._ready:
                self.repository.initialize()
                self._ready = True

    def page(self, **query):
        self.ensure()
        return {
            **self.repository.page(today=self.clock().date(), **query),
            "sync": self.repository.sync_status(),
        }

    def cities(self, search):
        self.ensure()
        return self.repository.cities(search)

    def status(self):
        self.ensure()
        return self.repository.sync_status()

    def calculate(self, identifier, tonnes):
        self.ensure()
        row = self.repository.detail(identifier)
        if row is None:
            raise LookupError("Tarifa não encontrada.")
        return {
            **estimate(row, tonnes, self.clock().date()),
            "presentePortal": row["presentePortal"],
        }

    async def _collect(self, lease):
        stage = "consulta_portal"
        try:
            raw, options = await self.collector(self.config)
            cities = portal_cities(options)
            lookup = {normalized(value["portal_label"]): value for value in cities}
            rows = [project(row, lookup) for row in raw]
            stage = "gravacao"
            if hasattr(self.repository, "progress"):
                await asyncio.to_thread(self.repository.progress, lease, stage)
            await asyncio.to_thread(
                self.repository.save, rows, cities, next_check(rows, self.clock()), lease
            )
        except asyncio.CancelledError:
            await asyncio.shield(
                asyncio.to_thread(
                    self.repository.fail, lease, "Coleta interrompida pelo encerramento do backend."
                )
            )
            raise
        except (PortalError, CommunicationUnavailable, ValueError, OSError) as exc:
            code = failure_code(exc, stage)
            text = failure_message(stage, code)
            message = (
                text
                + " O catálogo anterior foi preservado; nova tentativa automática em 15 minutos."
            )
            logger.warning(message)
            await asyncio.to_thread(self.repository.fail, lease, message, stage=stage, code=code)
        except Exception:  # noqa: BLE001 - redact unexpected portal/driver failures as well.
            # No raw exception can expose a cookie, password or response body.
            await asyncio.to_thread(
                self.repository.fail,
                lease,
                "Falha na leitura do tarifário. O catálogo anterior foi preservado.",
            )

    async def refresh(self, force=False):
        await asyncio.to_thread(self.ensure)
        if self._job is None or self._job.done():
            lease = await asyncio.to_thread(self.repository.claim, force)
            if lease:
                self._job = asyncio.create_task(self._collect(lease))
        return await asyncio.to_thread(self.repository.sync_status)

    async def refresh_and_wait(self, *, timeout_seconds=960, poll_seconds=2):
        """Wait for the shared import, including a lease held by another computer.

        A recent successful refresh may be reused during the existing 60-second
        cooldown. Failed imports never let the workflow continue with stale data.
        """
        async with asyncio.timeout(timeout_seconds):
            state = await self.refresh(force=True)
            while True:
                if self._job is not None:
                    await self._job
                    state = await asyncio.to_thread(self.repository.sync_status)
                if state["state"] == "completed":
                    return state
                if state["state"] in {"failed", "interrupted"}:
                    raise TariffRefreshError(state)
                await asyncio.sleep(poll_seconds)
                state = await asyncio.to_thread(self.repository.sync_status)

    async def loop(self):
        while True:
            try:
                await self.refresh()
            except (CommunicationUnavailable, OSError, ValueError):
                logger.warning("Catálogo de tarifas aguardando disponibilidade do banco e portal.")
            await asyncio.sleep(60)

    def start(self):
        enabled = str(self.config.get("NOVELIS_TARIFARIO_AUTO_SYNC") or "true").lower() in {
            "1",
            "true",
            "sim",
            "yes",
        }
        if enabled and self.repository.enabled:
            self._loop_task = asyncio.create_task(self.loop())

    async def close(self):
        for task in (self._loop_task, self._job):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, CommunicationUnavailable):
                    pass
