import asyncio
import logging
import sqlite3
from datetime import datetime, time, timedelta

from app.domain.automation_errors import AutomationBusyError

logger = logging.getLogger(__name__)
ACTIVE = {"running", "stopping"}


def scheduled_time(value: dict, now: datetime, offset: int = 0) -> datetime | None:
    day = now.date() + timedelta(days=offset)
    if day.weekday() not in value["weekdays"]:
        return None
    candidate = datetime.combine(day, time.fromisoformat(value["time"]), tzinfo=now.tzinfo)
    activated = datetime.fromisoformat(value["activated_at"])
    if candidate < activated:
        return None
    last = value.get("last_run")
    if last and last["local_date"] == day.isoformat():
        return None
    return candidate


class ScheduleEngine:
    def __init__(self, repository, hub, audit, events, clock=None):
        self.repository, self.hub, self.audit, self.events = repository, hub, audit, events
        self.clock = clock or (lambda: datetime.now().astimezone())
        identity = audit.identity()
        self.windows_user, self.device = identity["windows_user"], identity["computer_name"]
        self._tick_lock = asyncio.Lock()
        self._pending = []
        self.task: asyncio.Task | None = None

    def list(self, windows_user: str) -> dict:
        now = self.clock()
        values = self.repository.list(windows_user)
        for value in values:
            candidates = [scheduled_time(value, now, offset) for offset in range(8)] if value["enabled"] else []
            next_at = next((candidate for candidate in candidates if candidate is not None), None)
            value["next_run_at"] = next_at.isoformat() if next_at else None
        return {"schedules": values, "device": self.device, "local_time": now.isoformat()}

    def save(self, body, actor, identifier=None) -> dict:
        result = self.repository.save(body, actor, self.clock(), identifier)
        return next(value for value in self.list(actor["windows_user"])["schedules"] if value["id"] == result)

    async def recover(self) -> None:
        values = await asyncio.to_thread(self.repository.active, self.windows_user)
        for value in values:
            run = await asyncio.to_thread(self.repository.store.run_by_id, value["run_id"]) if value.get("run_id") else None
            confirmed = run and run["status"] in {"completed", "failed", "cancelled"}
            await asyncio.to_thread(self.repository.update, value["schedule_id"], value["local_date"],
                run["status"] if confirmed else "interrupted",
                run.get("message", "Execução encerrada.") if confirmed else "O backend reiniciou durante esta ocorrência. Confira o histórico de execução.", finished=True)
            if value.get("session_id"):
                await asyncio.to_thread(self.audit.logout, value["session_id"])

    async def _flush(self) -> None:
        while self._pending:
            identifier, day, run_id, session_id = self._pending[0]
            await asyncio.to_thread(self.repository.update, identifier, day, "running", "Execução agendada iniciada.",
                                    run_id=run_id, session_id=session_id)
            self._pending.pop(0)

    async def _finish(self) -> None:
        snapshot = (await self.hub.automation.current()).model_dump(mode="json")
        for value in await asyncio.to_thread(self.repository.active, self.windows_user):
            if not value.get("run_id"):
                continue
            run = snapshot if snapshot["id"] == value["run_id"] else await asyncio.to_thread(self.repository.store.run_by_id, value["run_id"])
            if run and run["status"] in ACTIVE and run["id"] == snapshot["id"]:
                continue
            state = run["status"] if run and run["status"] not in ACTIVE else "interrupted"
            message = run.get("message", "Execução encerrada.") if run else "Confira o resultado no histórico de execução."
            await asyncio.to_thread(self.repository.update, value["schedule_id"], value["local_date"], state, message, finished=True)
            if value.get("session_id"):
                await asyncio.to_thread(self.audit.logout, value["session_id"])

    async def _dispatch(self, value: dict, now: datetime) -> None:
        day = now.date().isoformat()
        if not await asyncio.to_thread(self.repository.claim, value, day, now):
            return
        session = None
        try:
            snapshot = (await self.hub.automation.current()).model_dump(mode="json")
            session = await asyncio.to_thread(self.audit.login, value["operator_name"] + " (agendado)", snapshot)
            await asyncio.to_thread(self.repository.update, value["id"], day, "starting", "Preparando execução agendada.", session_id=session["id"])
            current = await asyncio.to_thread(self.repository.list, self.windows_user)
            if not any(row["id"] == value["id"] and row["revision"] == value["revision"] and row["enabled"] for row in current):
                await asyncio.to_thread(self.repository.update, value["id"], day, "cancelled", "Configuração alterada antes do início.", finished=True)
                await asyncio.to_thread(self.audit.logout, session["id"])
                return
            days = value["days_back"] + 1 if value["days_back"] else 0
            run = await self.hub.start(value["flow"], [], days, session["id"], include_progress=False)
        except AutomationBusyError:
            await asyncio.to_thread(self.repository.release_claim, value["id"], day)
            if session:
                await asyncio.to_thread(self.audit.logout, session["id"])
            return
        except (OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
            logger.warning("Agendamento %s não pôde iniciar (%s).", value["id"], type(exc).__name__)
            await asyncio.to_thread(self.repository.update, value["id"], day, "failed", "Falha ao iniciar a execução agendada. Consulte os logs do backend.", finished=True)
            if session:
                await asyncio.to_thread(self.audit.logout, session["id"])
            return
        self._pending.append((value["id"], day, run["id"], session["id"]))
        await self._flush()
        await self.events.publish("Execução iniciada pelo agendamento.", run_id=run["id"], kind="schedule.started",
            payload={"schedule_id": value["id"], "name": value["name"], "flow": value["flow"], "days_back": value["days_back"]})

    async def tick(self) -> None:
        async with self._tick_lock:
            await self._flush()
            await self._finish()
            if (await self.hub.automation.current()).status in ACTIVE:
                return
            now = self.clock()
            for value in await asyncio.to_thread(self.repository.list, self.windows_user):
                due = scheduled_time(value, now)
                if value["enabled"] and due is not None and due <= now:
                    await self._dispatch(value, now)
                    return

    async def loop(self) -> None:
        while True:
            try:
                await self.tick()
            except (OSError, RuntimeError, ValueError, sqlite3.Error):
                logger.warning("Agendador aguardando disponibilidade do backend e do banco compartilhado.")
            await asyncio.sleep(15)

    def start(self) -> None:
        self.task = asyncio.create_task(self.loop())

    async def close(self) -> None:
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
