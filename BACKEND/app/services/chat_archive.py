"""Durable GNRE migration, post-confirmation delivery cleanup and 30-day expiry."""

import asyncio
import logging
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from psycopg.types.json import Jsonb

from app.domain.chat import ChatStorageError, cte_code
from app.services.chat_network import ChatNetworkDelivery
from app.services.chat_storage import ARCHIVE

logger = logging.getLogger(__name__)


class ChatArchive:
    def __init__(self, chat, operations):
        self.chat, self.operations = chat, operations
        self.task = None
        self.retention_ready = False

    def migrate(self, cte):
        files = self.chat.documents.files
        with self.chat.store.connection() as db:
            row = db.execute(
                "SELECT * FROM public.cargo_hub_chat_documents WHERE cte=%s FOR UPDATE", (cte,)
            ).fetchone()
            if not row or row["archive_state"] != "active":
                return
            updated = {}
            for kind in ("guia", "comprovante", "combined"):
                metadata = row.get(kind)
                if metadata:
                    metadata = dict(metadata)
                    if not metadata.get("object_key"):
                        data = files.read(cte, metadata)
                        files.write(cte, metadata, data)
                    updated[kind] = metadata
            if not updated:
                return
            db.execute(
                """UPDATE public.cargo_hub_chat_documents SET guia=%s,comprovante=%s,combined=%s,
                publish_state='pending' WHERE cte=%s""",
                (
                    Jsonb(updated.get("guia")),
                    Jsonb(updated.get("comprovante")),
                    Jsonb(updated.get("combined")),
                    cte,
                ),
            )
        self.chat.documents.publish(cte)

    def confirm(self, event):
        payload = event.get("payload") or {}
        result = payload.get("result") or {}
        ticket = payload.get("ticket") or {}
        number = str(
            payload.get("numeroChamado") or payload.get("number") or ticket.get("numero") or ""
        )
        if (
            event.get("kind") != "novelis.save"
            or result.get("ok") is not True
            or not number.isdigit()
        ):
            return
        try:
            cte = cte_code(payload.get("cte") or ticket.get("cte") or "")
        except ValueError:
            return
        confirmed = datetime.fromisoformat(event["created_at"])
        with self.chat.store.connection() as db:
            row = db.execute(
                "SELECT * FROM public.cargo_hub_chat_documents WHERE cte=%s FOR UPDATE", (cte,)
            ).fetchone()
            if (
                not row
                or not row.get("combined")
                or row["archive_state"] != "active"
                or confirmed < row["updated_at"]
            ):
                return
            if any(
                not row.get(kind, {}).get("object_key")
                for kind in ("guia", "comprovante", "combined")
            ):
                return
            db.execute(
                """UPDATE public.cargo_hub_chat_documents SET archive_state='requested',archive_id=%s,
                ticket_number=%s,confirmed_at=%s,expires_at=%s WHERE cte=%s""",
                (uuid4(), number, confirmed, confirmed + timedelta(days=30), cte),
            )

    def finalize(self, cte):
        files = self.chat.documents.files
        with self.chat.store.connection() as db:
            row = db.execute(
                "SELECT * FROM public.cargo_hub_chat_documents WHERE cte=%s FOR UPDATE", (cte,)
            ).fetchone()
            if row["archive_state"] == "requested":
                try:
                    updated = files.objects.archive(row)
                except Exception:  # noqa: BLE001 - keep storage/provider errors out of database diagnostics
                    raise ChatStorageError(
                        "O arquivamento no MinIO está pendente. A cópia de rede foi preservada."
                    ) from None
                db.execute(
                    """UPDATE public.cargo_hub_chat_documents SET guia=%s,comprovante=%s,combined=%s,
                    archive_state='cleanup' WHERE cte=%s""",
                    (
                        Jsonb(updated.get("guia")),
                        Jsonb(updated.get("comprovante")),
                        Jsonb(updated.get("combined")),
                        cte,
                    ),
                )
        with self.chat.store.connection() as db:
            row = db.execute(
                "SELECT * FROM public.cargo_hub_chat_documents WHERE cte=%s FOR UPDATE", (cte,)
            ).fetchone()
            if row["archive_state"] == "cleanup":
                ChatNetworkDelivery(files).cleanup(row)
                files.objects.remove_pending(cte)
                db.execute(
                    "UPDATE public.cargo_hub_chat_documents SET archive_state='archived',publish_state='ready' WHERE cte=%s",
                    (cte,),
                )

    def expire(self, cte):
        files = self.chat.documents.files
        with self.chat.store.connection() as db:
            row = db.execute(
                "SELECT * FROM public.cargo_hub_chat_documents WHERE cte=%s FOR UPDATE", (cte,)
            ).fetchone()
            if (
                row["archive_state"] != "archived"
                or not row["expires_at"]
                or row["expires_at"] > datetime.now(UTC)
            ):
                return
            prefix = f"{ARCHIVE}{cte_code(cte)}/{row['archive_id']}/"
            from app.services.releases.config import BUCKET

            for key in files.objects.objects(prefix):
                files.objects.valid_key(cte, key)
                files.objects.client().delete_object(Bucket=BUCKET, Key=key)
            db.execute(
                "UPDATE public.cargo_hub_chat_documents SET archive_state='expired' WHERE cte=%s",
                (cte,),
            )

    def tick(self):
        if not self.chat.store.db.enabled:
            return
        if not self.retention_ready:
            self.chat.documents.files.objects.ensure_retention()
            self.retention_ready = True
        with self.chat.store.connection() as db:
            rows = db.execute("""SELECT cte FROM public.cargo_hub_chat_documents WHERE archive_state='active'
                AND (guia IS NOT NULL AND NOT (guia ? 'object_key')
                OR comprovante IS NOT NULL AND NOT (comprovante ? 'object_key')
                OR combined IS NOT NULL AND NOT (combined ? 'object_key')) LIMIT 50""").fetchall()
        for row in rows:
            try:
                self.migrate(row["cte"])
            except (ChatStorageError, OSError):
                logger.warning("GNRE: migração pendente; arquivos anteriores preservados.")
        with self.chat.store.connection() as db:
            pending = db.execute(
                "SELECT cte FROM public.cargo_hub_chat_documents WHERE archive_state='active' AND publish_state='pending'"
            ).fetchall()
        for row in pending:
            try:
                self.chat.documents.publish(row["cte"])
            except (ChatStorageError, OSError):
                logger.warning("GNRE: entrega do PDF unificado na rede aguardando nova tentativa.")
        if self.operations:
            with self.chat.store.connection() as db:
                active = db.execute(
                    "SELECT cte FROM public.cargo_hub_chat_documents WHERE archive_state='active' AND combined IS NOT NULL"
                ).fetchall()
            for event in self.operations.confirmed_ticket_events([row["cte"] for row in active]):
                self.confirm(event)
        with self.chat.store.connection() as db:
            jobs = db.execute(
                "SELECT cte,archive_state FROM public.cargo_hub_chat_documents WHERE archive_state IN ('requested','cleanup','archived')"
            ).fetchall()
        for job in jobs:
            try:
                self.expire(job["cte"]) if job["archive_state"] == "archived" else self.finalize(
                    job["cte"]
                )
            except (ChatStorageError, OSError):
                logger.warning("GNRE: entrega ou limpeza de rede aguardando nova tentativa.")

    def start(self):
        async def loop():
            while True:
                try:
                    await asyncio.to_thread(self.tick)
                except Exception:  # noqa: BLE001 - background maintenance must retry provider failures
                    logger.warning(
                        "GNRE: sincronização com MinIO pendente. Nova tentativa em 60 segundos."
                    )
                await asyncio.sleep(60)

        self.task = asyncio.create_task(loop())

    async def close(self):
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
