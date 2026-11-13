import asyncio
import logging
import sqlite3
from datetime import UTC, datetime

from app.domain.models import RunSnapshot, RunStatus
from app.services.session_audit import operator_session


class RunState:
    def __init__(self, store=None, audit=None) -> None:
        self._lock = asyncio.Lock()
        self._snapshot = RunSnapshot()
        self.store = store
        self.audit = audit

    async def restore(self) -> None:
        if self.store:
            value = await asyncio.to_thread(self.store.last_run)
            if value:
                self._snapshot = RunSnapshot(**value)
                if self._snapshot.status in {"running", "stopping"}:
                    await self.update(status="failed", message="Backend reiniciado antes de concluir a execucao.")

    async def _persist(self) -> None:
        if self.store:
            await asyncio.to_thread(self.store.save_run, self._snapshot.model_dump(mode="json"))
        if self.audit:
            try:
                await asyncio.to_thread(self.audit.record_run, self._snapshot.model_dump(mode="json"), operator_session.get())
            except (OSError, RuntimeError, sqlite3.Error):
                logging.getLogger(__name__).warning("Falha ao registrar o estado da automacao na fila local de auditoria.")

    async def get(self) -> RunSnapshot:
        async with self._lock:
            return self._snapshot.model_copy(deep=True)

    async def start(self, flow: str, dry_run: bool) -> RunSnapshot:
        async with self._lock:
            if self._snapshot.status in {"running", "stopping"}:
                raise RuntimeError("Já existe uma execução ativa.")
            self._snapshot = RunSnapshot(
                status="running",
                flow=flow,
                dry_run=dry_run,
                message="Execução iniciada.",
                started_at=datetime.now(UTC),
            )
            await self._persist()
            return self._snapshot.model_copy(deep=True)

    async def update(
        self,
        *,
        status: RunStatus | None = None,
        current_step: int | None = None,
        message: str | None = None,
    ) -> RunSnapshot:
        async with self._lock:
            data = self._snapshot.model_dump()
            if status is not None:
                data["status"] = status
            if current_step is not None:
                data["current_step"] = current_step
            if message is not None:
                data["message"] = message
            if status in {"completed", "failed", "cancelled"}:
                data["finished_at"] = datetime.now(UTC)
            self._snapshot = RunSnapshot(**data)
            await self._persist()
            return self._snapshot.model_copy(deep=True)

    async def request_stop(self) -> RunSnapshot:
        async with self._lock:
            if self._snapshot.status == "running":
                data = self._snapshot.model_dump()
                data["status"] = "stopping"
                data["message"] = "Parada solicitada."
                self._snapshot = RunSnapshot(**data)
                await self._persist()
            return self._snapshot.model_copy(deep=True)
