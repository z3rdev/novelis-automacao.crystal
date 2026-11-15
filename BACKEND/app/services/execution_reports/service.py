import asyncio
import sqlite3
from contextlib import suppress
from datetime import datetime
from hashlib import sha256

from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import BotoCoreError, ClientError

from app.services.session_audit import operator_session

from .daily import DailyReports
from .daily_models import confirmed_at, daily_id
from .models import entries, identifier, public, timestamp
from .repository import ReportRepository
from .storage import ReportStorage
from .workbook import ZONE, build


class ExecutionReports:
    def __init__(self, settings, config, store, audit=None, storage=None):
        self.repository = ReportRepository(store)
        self.audit, self.store = audit, store
        self.root = store.path.parent / "logs" / "relatorios-execucoes"
        self.storage = storage or ReportStorage(settings.backend_root, config)
        self.daily = DailyReports(self.repository, self.root, self.storage)
        self._loop, self._job = None, None
        self._closing = False

    def file(self, run_id):
        return self.root / f"{identifier(run_id)}.xlsx"

    async def begin(self, snapshot, request):
        custom_tickets = (
            request.flow == "workflow"
            and request.workflow
            and any(
                node.kind in {"tickets", "generate_report", "completion_modal"}
                for node in request.workflow.nodes
            )
        )
        if (
            request.dry_run
            or request.flow
            not in {
                "pendentes",
                "chamado-novelis",
                "chamado-http",
                "novelis",
            }
            and not custom_tickets
        ):
            return
        if request.flow == "pendentes" and request.execution_scope not in {"full", "chamados"}:
            return
        session_id = operator_session.get()
        actor = (
            await asyncio.to_thread(self.audit.session, session_id)
            if self.audit and session_id
            else None
        )
        fallback = (
            self.audit.identity().get("windows_user", "Automático") if self.audit else "Automático"
        )
        value = {
            "id": snapshot.id,
            "operator": (actor or {}).get("operator_name") or fallback,
            "computer": self.store.machine_id,
            "flow": request.flow,
            "status": "running",
            "started_at": snapshot.started_at.isoformat(),
            "finished_at": None,
            "generated_at": timestamp(),
            "opened_count": 0,
            "existing_count": 0,
            "opened": [],
            "existing": [],
            "share_status": "pending",
            "share_message": "Execução em andamento.",
            "generate_requested": bool(
                request.workflow
                and any(node.kind == "generate_report" for node in request.workflow.nodes)
            ),
        }
        await asyncio.to_thread(self.repository.save, value)

    async def finish(self, snapshot):
        value = await asyncio.to_thread(self.repository.get, snapshot.id)
        if not value:
            return
        events = await asyncio.to_thread(self.repository.events, snapshot.id)
        opened, existing = entries(events)
        value.update(
            status=snapshot.status,
            finished_at=snapshot.finished_at.isoformat(),
            generated_at=timestamp(),
            opened=opened,
            existing=existing,
            opened_count=len(opened),
            existing_count=len(existing),
            share_status="pending",
            share_message="Resultados incorporados ao relatório diário de chamados.",
        )
        for key in ("sha256", "private_url", "private_url_expires", "object_key"):
            value.pop(key, None)
        if value.get("generate_requested"):
            value["requested_report_date"] = max(
                (confirmed_at(item, value).astimezone(ZONE).date().isoformat() for item in opened),
                default=datetime.fromisoformat(value["finished_at"])
                .astimezone(ZONE)
                .date()
                .isoformat(),
            )
        await asyncio.to_thread(self.repository.save, value)
        await asyncio.to_thread(self.daily.refresh)
        self.sync()
        dates = {confirmed_at(item, value).astimezone(ZONE).date().isoformat() for item in opened}
        if value.get("requested_report_date"):
            dates.add(value["requested_report_date"])
        return {
            **public(value),
            "daily_reports": [{"id": daily_id(day), "report_date": day} for day in sorted(dates)],
        }

    def page(self, page=0):
        self.daily.refresh()
        value = self.daily.repository.page(page)
        return {**value, "rows": [public(row) for row in value["rows"]]}

    def detail(self, run_id):
        self.daily.refresh()
        if value := self.daily.repository.get(run_id):
            return public(value, detail=True)
        value = self.repository.get(run_id)
        if not value or value["status"] == "running":
            raise LookupError("Relatório não encontrado.")
        return public(value, detail=True)

    def download(self, run_id):
        self.daily.refresh()
        if self.daily.repository.get(run_id):
            return self.daily.download(run_id)
        value = self.repository.get(run_id)
        if not value or value["status"] == "running":
            raise LookupError("Relatório não encontrado.")
        # Historical UUID links remain usable, with their Excel generated on demand.
        file = self.file(run_id)
        if not value.get("sha256") or not file.is_file():
            build(value, file)
            value["sha256"] = sha256(file.read_bytes()).hexdigest()
            self.repository.save(value)
        return self.storage.retrieve(value, file)

    async def _publish_pending(self):
        from app.domain.models import RunSnapshot

        for snapshot in await asyncio.to_thread(self.repository.unfinished):
            try:
                await self.finish(RunSnapshot(**snapshot))
            except (OSError, RuntimeError, sqlite3.Error, ValueError):
                continue
        await asyncio.to_thread(self.daily.refresh)
        report_ids = await asyncio.to_thread(self.daily.repository.pending)
        for report_id in report_ids:
            try:
                await asyncio.to_thread(self.daily.publish, report_id)
            except (
                BotoCoreError,
                ClientError,
                S3UploadFailedError,
                OSError,
                RuntimeError,
                ValueError,
                ImportError,
            ):
                continue

    def sync(self):
        if self._closing:
            return
        if not self._job or self._job.done():

            async def attempt():
                with suppress(OSError, RuntimeError, sqlite3.Error):
                    await self._publish_pending()

            self._job = asyncio.create_task(attempt())

    def start(self):
        async def loop():
            while True:
                self.sync()
                await asyncio.sleep(60)

        self._loop = asyncio.create_task(loop())

    async def close(self):
        self._closing = True
        for task in (self._loop, self._job):
            if task and not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
