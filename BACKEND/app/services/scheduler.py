import asyncio
import logging
import sqlite3
from datetime import datetime

from app.domain.automation_errors import AutomationBusyError
from app.services.schedule_timing import next_occurrence

logger = logging.getLogger(__name__)
ACTIVE = {"running", "stopping"}


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
            occurrence = next_occurrence(value, now)
            value["next_run_at"] = occurrence["due_at"].isoformat() if occurrence else None
            value["next_attempt"] = occurrence["attempt"] + 1 if occurrence else None
            value["next_slot"] = occurrence["slot"] + 1 if occurrence else None
            value.pop("occurrences", None)
        return {
            "schedules": values,
            "device": self.device,
            "local_time": now.isoformat(),
            "running": self.task is not None and not self.task.done(),
        }

    def save(self, body, actor, identifier=None) -> dict:
        result = self.repository.save(body, actor, self.clock(), identifier)
        return next(
            value
            for value in self.list(actor["windows_user"])["schedules"]
            if value["id"] == result
        )

    async def _start_flow(self, value, session_id, *, include_progress=False):
        days = value["days_back"] + 1 if value["days_back"] else 0
        options = {"workflow": value.get("workflow")} if value["flow"] == "personalizado" else {}
        return await self.hub.start(
            value["flow"], [], days, session_id, include_progress=include_progress, **options
        )

    async def run_now(self, identifier, actor):
        values = await asyncio.to_thread(self.repository.list, actor["windows_user"])
        value = next((row for row in values if row["id"] == identifier), None)
        if value is None:
            raise KeyError(identifier)
        result = await self._start_flow(value, actor["id"], include_progress=True)
        await self.events.publish(
            "Rotina iniciada manualmente pelo operador.",
            run_id=result["id"],
            kind="schedule.manual_started",
            payload={"schedule_id": identifier, "name": value["name"], "flow": value["flow"]},
        )
        return result

    async def recover(self) -> None:
        values = await asyncio.to_thread(self.repository.active, self.windows_user)
        for value in values:
            run = (
                await asyncio.to_thread(self.repository.store.run_by_id, value["run_id"])
                if value.get("run_id")
                else None
            )
            confirmed = run and run["status"] in {"completed", "failed", "cancelled"}
            await asyncio.to_thread(
                self.repository.update,
                value["schedule_id"],
                value["local_date"],
                run["status"] if confirmed else "interrupted",
                run.get("message", "Execução encerrada.")
                if confirmed
                else "O backend reiniciou durante esta ocorrência. Confira o histórico de execução.",
                finished=True,
                slot=value["slot"],
                attempt=value["attempt"],
                now=self.clock(),
            )
            if value.get("session_id"):
                await asyncio.to_thread(self.audit.logout, value["session_id"])

    async def _flush(self) -> None:
        while self._pending:
            identifier, occurrence, run_id, session_id = self._pending[0]
            await asyncio.to_thread(
                self.repository.update,
                identifier,
                occurrence["local_date"],
                "running",
                "Execução agendada iniciada.",
                run_id=run_id,
                session_id=session_id,
                slot=occurrence["slot"],
                attempt=occurrence["attempt"],
            )
            self._pending.pop(0)

    async def _finish(self) -> None:
        snapshot = (await self.hub.automation.current()).model_dump(mode="json")
        for value in await asyncio.to_thread(self.repository.active, self.windows_user):
            if not value.get("run_id"):
                continue
            run = (
                snapshot
                if snapshot["id"] == value["run_id"]
                else await asyncio.to_thread(self.repository.store.run_by_id, value["run_id"])
            )
            if run and run["status"] in ACTIVE and run["id"] == snapshot["id"]:
                continue
            state = run["status"] if run and run["status"] not in ACTIVE else "interrupted"
            message = (
                run.get("message", "Execução encerrada.")
                if run
                else "Confira o resultado no histórico de execução."
            )
            queued = await asyncio.to_thread(
                self.repository.update,
                value["schedule_id"],
                value["local_date"],
                state,
                message,
                finished=True,
                slot=value["slot"],
                attempt=value["attempt"],
                now=self.clock(),
            )
            if queued:
                await self.events.publish(
                    "Rotina falhou. Nova tentativa agendada conforme a configuração.",
                    run_id=value.get("run_id"),
                    kind="schedule.retry_scheduled",
                    level="warn",
                    payload={
                        "schedule_id": value["schedule_id"],
                        "slot": value["slot"] + 1,
                        "attempt": value["attempt"] + 2,
                    },
                )
            if value.get("session_id"):
                await asyncio.to_thread(self.audit.logout, value["session_id"])

    async def _dispatch(self, value: dict, now: datetime, occurrence: dict) -> None:
        day = occurrence["local_date"]
        key = {"slot": occurrence["slot"], "attempt": occurrence["attempt"]}
        if not await asyncio.to_thread(
            self.repository.claim, value, day, now, due_at=occurrence["due_at"], **key
        ):
            return
        session = None
        try:
            snapshot = (await self.hub.automation.current()).model_dump(mode="json")
            session = await asyncio.to_thread(
                self.audit.login, value["operator_name"] + " (agendado)", snapshot
            )
            await asyncio.to_thread(
                self.repository.update,
                value["id"],
                day,
                "starting",
                "Preparando execução agendada.",
                session_id=session["id"],
                **key,
            )
            current = await asyncio.to_thread(self.repository.list, self.windows_user)
            if not any(
                row["id"] == value["id"] and row["revision"] == value["revision"] and row["enabled"]
                for row in current
            ):
                await asyncio.to_thread(
                    self.repository.update,
                    value["id"],
                    day,
                    "cancelled",
                    "Configuração alterada antes do início.",
                    finished=True,
                    now=now,
                    **key,
                )
                await asyncio.to_thread(self.audit.logout, session["id"])
                return
            run = await self._start_flow(value, session["id"])
        except AutomationBusyError:
            await asyncio.to_thread(self.repository.release_claim, value["id"], day, **key)
            if session:
                await asyncio.to_thread(self.audit.logout, session["id"])
            return
        except (OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
            logger.warning("Agendamento %s não pôde iniciar (%s).", value["id"], type(exc).__name__)
            await asyncio.to_thread(
                self.repository.update,
                value["id"],
                day,
                "failed",
                "Falha ao iniciar a execução agendada. Consulte os logs do backend.",
                finished=True,
                now=now,
                **key,
            )
            if session:
                await asyncio.to_thread(self.audit.logout, session["id"])
            return
        self._pending.append((value["id"], occurrence, run["id"], session["id"]))
        await self._flush()
        await self.events.publish(
            "Execução iniciada pelo agendamento.",
            run_id=run["id"],
            kind="schedule.started",
            payload={
                "schedule_id": value["id"],
                "name": value["name"],
                "flow": value["flow"],
                "days_back": value["days_back"],
                "slot": occurrence["slot"] + 1,
                "runs_per_day": value["runs_per_day"],
                "attempt": occurrence["attempt"] + 1,
                "max_attempts": value["max_retries"] + 1,
            },
        )

    async def tick(self) -> None:
        async with self._tick_lock:
            await self._flush()
            await self._finish()
            if (await self.hub.automation.current()).status in ACTIVE:
                return
            now = self.clock()
            candidates = []
            for value in await asyncio.to_thread(self.repository.list, self.windows_user):
                due = next_occurrence(value, now, today_only=True)
                if due is not None and due["due_at"] <= now:
                    candidates.append((value, due))
            if candidates:
                value, due = min(candidates, key=lambda item: item[1]["due_at"])
                await self._dispatch(value, now, due)

    async def loop(self) -> None:
        while True:
            try:
                await self.tick()
            except (OSError, RuntimeError, ValueError, sqlite3.Error):
                logger.warning(
                    "Agendador aguardando disponibilidade do backend e do banco compartilhado."
                )
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
