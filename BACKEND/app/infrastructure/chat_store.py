from contextlib import contextmanager
from datetime import datetime
from threading import Lock
from uuid import UUID

from app.domain.chat import ChatError, ChatNotFound
from app.infrastructure.chamados_postgres import ChamadosPostgres, CommunicationUnavailable
from app.infrastructure.chat_schema import ACCESS, SCHEMA, access_params


def serialize(value):
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialize(item) for item in value]
    return (
        value.isoformat()
        if isinstance(value, datetime)
        else str(value)
        if isinstance(value, UUID)
        else value
    )


class ChatStore:
    def __init__(self, config):
        self.db = ChamadosPostgres(config)
        self.ready, self.lock = False, Lock()

    def ensure(self):
        if not self.db.enabled:
            raise CommunicationUnavailable(
                "Configure o banco de comunicação para usar as mensagens."
            )
        with self.lock:
            if not self.ready:
                with self.db.connection() as db:
                    db.execute("SELECT pg_advisory_xact_lock(14591378)")
                    db.execute(SCHEMA)
                self.ready = True

    @contextmanager
    def connection(self):
        self.ensure()
        error = None
        with self.db.connection() as db:
            try:
                yield db
            except ChatError as exc:
                db.rollback()
                error = exc
        if error:
            raise error

    @staticmethod
    def room(db, identifier, actor, *, lock=False):
        row = db.execute(
            f"SELECT r.* FROM public.cargo_hub_chat_rooms r WHERE r.id=%s AND {ACCESS}"
            + (" FOR UPDATE" if lock else ""),
            (identifier, *access_params(actor)),
        ).fetchone()
        if not row:
            raise ChatNotFound("Conversa não encontrada para esta conta e setor.")
        return row

    def register(self, actor):
        with self.connection() as db:
            db.execute(
                """INSERT INTO public.cargo_hub_chat_people(user_key,windows_user,name,sector,device)
                VALUES(%s,%s,%s,%s,%s) ON CONFLICT(user_key) DO UPDATE SET windows_user=excluded.windows_user,
                name=excluded.name,sector=excluded.sector,device=excluded.device,seen_at=now()""",
                (
                    actor["key"],
                    actor["windows_user"],
                    actor["name"],
                    actor.get("sector"),
                    actor["device"],
                ),
            )

    def people(self):
        with self.connection() as db:
            return serialize(
                db.execute("""SELECT user_key AS key,windows_user,name,sector,
                seen_at>now()-interval '90 seconds' AS online FROM public.cargo_hub_chat_people
                ORDER BY name,user_key""").fetchall()
            )
