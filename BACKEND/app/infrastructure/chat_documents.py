from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from app.domain.chat import ChatConflict, ChatNotFound
from app.infrastructure.chat_rooms import ChatRooms
from app.infrastructure.chat_store import serialize
from app.services.chat_files import merge_pdfs


class ChatDocuments:
    def __init__(self, store, files):
        self.store, self.files = store, files

    def create(self, room_id, actor, body):
        with self.store.connection() as db:
            self.store.room(db, room_id, actor, lock=True)
            row = db.execute(
                "SELECT * FROM public.cargo_hub_chat_requests WHERE room_id=%s AND cte=%s",
                (room_id, body.cte),
            ).fetchone()
            if not row:
                db.execute(
                    "INSERT INTO public.cargo_hub_chat_documents(cte) VALUES(%s) ON CONFLICT DO NOTHING",
                    (body.cte,),
                )
                row = db.execute(
                    """INSERT INTO public.cargo_hub_chat_requests
                    (id,room_id,cte,note,chamado,requested_by,requested_name) VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                    (
                        uuid4(),
                        room_id,
                        body.cte,
                        body.note.strip(),
                        body.chamado,
                        actor["key"],
                        actor["name"],
                    ),
                ).fetchone()
            ChatRooms.insert_message(
                db,
                room_id,
                actor,
                body.client_id,
                f"Solicitação de guia GNRE e comprovante · CT-e {body.cte}",
                "request",
                row["id"],
            )
        return serialize(row)

    @staticmethod
    def rows(db, room_id, identifiers=None):
        return db.execute(
            """SELECT q.*,d.guia,d.comprovante,d.combined,d.publish_state,d.updated_at,
            d.archive_state,d.confirmed_at,d.expires_at
            FROM public.cargo_hub_chat_requests q JOIN public.cargo_hub_chat_documents d USING(cte)
            WHERE q.room_id=%s AND (%s::uuid[] IS NULL OR q.id=ANY(%s::uuid[]))
            ORDER BY q.created_at DESC LIMIT 100""",
            (room_id, identifiers, identifiers),
        ).fetchall()

    def view(self, row):
        value = serialize(dict(row))
        value["state"] = (
            "expired"
            if row.get("expires_at") and row["expires_at"] <= datetime.now(UTC)
            else "archived"
            if row.get("archive_state") in {"cleanup", "archived"}
            else "publishing"
            if row.get("publish_state") != "ready"
            else "available"
            if row.get("guia") and row.get("comprovante") and row.get("combined")
            else "partial"
            if row.get("guia") or row.get("comprovante")
            else "in_progress"
            if row.get("assigned_to")
            else "waiting"
        )
        value["directory"] = str(self.files.directory(row["cte"]))
        value["chamado_url"] = (
            f"https://novelis.wtmh.com.br/portal/chamado/{row['chamado']}"
            if row.get("chamado")
            else None
        )
        return value

    def get_request(self, db, room_id, identifier, actor):
        self.store.room(db, room_id, actor)
        row = db.execute(
            "SELECT * FROM public.cargo_hub_chat_requests WHERE id=%s AND room_id=%s",
            (identifier, room_id),
        ).fetchone()
        if not row:
            raise ChatNotFound("Solicitação não encontrada nesta conversa.")
        return row

    def claim(self, room_id, identifier, actor):
        with self.store.connection() as db:
            self.store.room(db, room_id, actor, lock=True)
            self.get_request(db, room_id, identifier, actor)
            row = db.execute(
                """UPDATE public.cargo_hub_chat_requests SET assigned_to=%s,assigned_name=%s
                WHERE id=%s AND (assigned_to IS NULL OR assigned_to=%s) RETURNING *""",
                (actor["key"], actor["name"], identifier, actor["key"]),
            ).fetchone()
            if not row:
                raise ChatConflict("Outro operador já assumiu esta solicitação.")

    def upload(self, room_id, identifier, actor, kind, client_id, original_name, data):
        from psycopg.types.json import Jsonb

        with self.store.connection() as db:
            self.store.room(db, room_id, actor, lock=True)
            request = self.get_request(db, room_id, identifier, actor)
            row = db.execute(
                "SELECT * FROM public.cargo_hub_chat_documents WHERE cte=%s FOR UPDATE",
                (request["cte"],),
            ).fetchone()
            duplicate = db.execute(
                "SELECT * FROM public.cargo_hub_chat_messages WHERE sender=%s AND client_id=%s",
                (actor["key"], client_id),
            ).fetchone()
            label = "Guia GNRE" if kind == "guia" else "Comprovante de pagamento"
            body = f"{label} enviado · CT-e {request['cte']}"
            if duplicate:
                if str(duplicate["request_id"]) != str(identifier) or duplicate["body"] != body:
                    raise ChatConflict("Esta tentativa já foi usada para outro documento.")
                current = row.get(kind)
                if (
                    current
                    and current["id"] == str(client_id)
                    and current["sha256"] != sha256(data).hexdigest()
                ):
                    raise ChatConflict("O arquivo mudou. Inicie um novo envio.")
            else:
                metadata = {
                    "id": str(client_id),
                    "kind": kind,
                    "sha256": sha256(data).hexdigest(),
                    "original_name": original_name.replace("\\", "/").rsplit("/", 1)[-1][:180],
                    "uploaded_by": actor["key"],
                    "uploaded_name": actor["name"],
                    "uploaded_at": datetime.now(UTC).isoformat(),
                }
                self.files.write(request["cte"], metadata, data)
                updated = {**row, kind: metadata, "generation": uuid4(), "combined": None}
                for other in {"guia", "comprovante"} - {kind}:
                    previous = updated.get(other)
                    if (
                        previous
                        and row.get("expires_at")
                        and row["expires_at"] <= datetime.now(UTC)
                    ):
                        updated[other] = None
                    elif previous and previous.get("expires_at"):
                        data = self.files.read(request["cte"], previous)
                        updated[other] = {
                            key: value for key, value in previous.items() if key != "expires_at"
                        }
                        self.files.write(request["cte"], updated[other], data)
                if updated["guia"] and updated["comprovante"]:
                    merged = merge_pdfs(
                        self.files.read(request["cte"], updated["guia"]),
                        self.files.read(request["cte"], updated["comprovante"]),
                    )
                    updated["combined"] = {
                        "id": str(uuid4()),
                        "kind": "combined",
                        "sha256": sha256(merged).hexdigest(),
                    }
                    self.files.write(request["cte"], updated["combined"], merged)
                db.execute(
                    """UPDATE public.cargo_hub_chat_documents SET guia=%s,comprovante=%s,combined=%s,
                    generation=%s,publish_state='pending',updated_at=now(),archive_state='active',
                    archive_id=NULL,confirmed_at=NULL,expires_at=NULL,ticket_number=NULL WHERE cte=%s""",
                    (
                        Jsonb(updated["guia"]),
                        Jsonb(updated["comprovante"]),
                        Jsonb(updated["combined"]),
                        updated["generation"],
                        request["cte"],
                    ),
                )
                ChatRooms.insert_message(
                    db, room_id, actor, client_id, body, "attachment", identifier
                )
        self.publish(request["cte"])

    def publish(self, cte):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT * FROM public.cargo_hub_chat_documents WHERE cte=%s FOR UPDATE", (cte,)
            ).fetchone()
            if (
                row
                and row["publish_state"] == "pending"
                and row.get("archive_state", "active") == "active"
            ):
                self.files.publish(row)
                db.execute(
                    "UPDATE public.cargo_hub_chat_documents SET publish_state='ready' WHERE cte=%s",
                    (cte,),
                )

    def download(self, room_id, identifier, actor, kind):
        with self.store.connection() as db:
            request = self.get_request(db, room_id, identifier, actor)
            row = db.execute(
                "SELECT * FROM public.cargo_hub_chat_documents WHERE cte=%s", (request["cte"],)
            ).fetchone()
        metadata = row.get(kind)
        if row.get("expires_at") and row["expires_at"] <= datetime.now(UTC):
            from app.domain.chat import ChatStorageError

            raise ChatStorageError("O prazo de armazenamento de 30 dias deste documento terminou.")
        if not metadata:
            raise ChatNotFound("Documento ainda não enviado.")
        return self.files.read(request["cte"], metadata), self.files.path(
            request["cte"], metadata
        ).name
