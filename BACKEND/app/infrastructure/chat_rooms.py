from hashlib import sha256
from uuid import uuid4

from app.domain.chat import ChatConflict, ChatError
from app.infrastructure.chat_schema import ACCESS, access_params
from app.infrastructure.chat_store import serialize


class ChatRooms:
    def __init__(self, store):
        self.store = store

    def create(self, body, actor, sectors):
        target = body.target.strip()
        if body.target_type == "sector":
            target = target.upper()
            if target not in sectors:
                raise ChatError("Selecione um setor válido.")
            key = f"sector:{target}:{actor['key']}"
        else:
            target = target.casefold()
            if target == actor["key"]:
                raise ChatError("Selecione outro operador.")
            key = (
                "operator:" + sha256("|".join(sorted([target, actor["key"]])).encode()).hexdigest()
            )
        with self.store.connection() as db:
            if (
                body.target_type == "operator"
                and not db.execute(
                    "SELECT 1 FROM public.cargo_hub_chat_people WHERE user_key=%s AND sector='FIN' AND seen_at>now()-interval '90 seconds'",
                    (target,),
                ).fetchone()
            ):
                raise ChatError("Selecione um operador online do Financeiro.")
            row = db.execute(
                """INSERT INTO public.cargo_hub_chat_rooms(id,room_key,target_type,target,creator)
                VALUES(%s,%s,%s,%s,%s) ON CONFLICT(room_key) DO UPDATE SET room_key=excluded.room_key RETURNING *""",
                (uuid4(), key, body.target_type, target, actor["key"]),
            ).fetchone()
        return serialize(row)

    def inbox(self, actor):
        with self.store.connection() as db:
            rows = db.execute(
                f"""SELECT r.*, creator.name AS creator_name, recipient.name AS target_name,
                preview.body AS last_message, preview.created_at AS last_message_at,
                (SELECT COALESCE(max(m.seq),0) FROM public.cargo_hub_chat_messages m
                  WHERE m.room_id=r.id AND m.sender<>%s AND m.seq>COALESCE(seen.through,0)) AS unread_seq,
                (SELECT count(*) FROM public.cargo_hub_chat_messages m
                  WHERE m.room_id=r.id AND m.sender<>%s AND m.seq>COALESCE(seen.through,0)) AS unread
                FROM public.cargo_hub_chat_rooms r
                LEFT JOIN public.cargo_hub_chat_people creator ON creator.user_key=r.creator
                LEFT JOIN public.cargo_hub_chat_people recipient ON recipient.user_key=r.target
                LEFT JOIN public.cargo_hub_chat_reads seen ON seen.room_id=r.id AND seen.user_key=%s
                LEFT JOIN LATERAL (SELECT body,created_at FROM public.cargo_hub_chat_messages
                  WHERE room_id=r.id ORDER BY seq DESC LIMIT 1) preview ON true
                WHERE {ACCESS} ORDER BY r.updated_at DESC,r.id""",
                (actor["key"], actor["key"], actor["key"], *access_params(actor)),
            ).fetchall()
        return serialize(rows)

    @staticmethod
    def insert_message(db, room_id, actor, client_id, body, kind="text", request_id=None):
        existing = db.execute(
            "SELECT * FROM public.cargo_hub_chat_messages WHERE sender=%s AND client_id=%s",
            (actor["key"], client_id),
        ).fetchone()
        if existing:
            if (
                str(existing["room_id"]) != str(room_id)
                or existing["body"] != body
                or existing["kind"] != kind
            ):
                raise ChatConflict("Esta tentativa já foi usada para outra mensagem.")
            return existing
        row = db.execute(
            """INSERT INTO public.cargo_hub_chat_messages
            (id,room_id,sender,sender_name,client_id,body,kind,request_id) VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (uuid4(), room_id, actor["key"], actor["name"], client_id, body, kind, request_id),
        ).fetchone()
        db.execute(
            "UPDATE public.cargo_hub_chat_rooms SET updated_at=now() WHERE id=%s", (room_id,)
        )
        return row

    def send(self, room_id, actor, body):
        with self.store.connection() as db:
            self.store.room(db, room_id, actor, lock=True)
            row = self.insert_message(db, room_id, actor, body.client_id, body.body)
        return serialize(row)

    @staticmethod
    def page(db, room_id, before=None):
        rows = db.execute(
            """SELECT * FROM public.cargo_hub_chat_messages WHERE room_id=%s
            AND (%s::bigint IS NULL OR seq<%s) ORDER BY seq DESC LIMIT 101""",
            (room_id, before, before),
        ).fetchall()
        page = rows[:100]
        return {
            "messages": serialize(list(reversed(page))),
            "before": page[-1]["seq"] if len(rows) > 100 else None,
        }

    def read(self, room_id, actor, through):
        with self.store.connection() as db:
            self.store.room(db, room_id, actor)
            latest = db.execute(
                "SELECT COALESCE(max(seq),0) AS seq FROM public.cargo_hub_chat_messages WHERE room_id=%s",
                (room_id,),
            ).fetchone()["seq"]
            db.execute(
                """INSERT INTO public.cargo_hub_chat_reads(room_id,user_key,through) VALUES(%s,%s,%s)
                ON CONFLICT(room_id,user_key) DO UPDATE SET through=GREATEST(cargo_hub_chat_reads.through,excluded.through)""",
                (room_id, actor["key"], min(through, latest)),
            )
