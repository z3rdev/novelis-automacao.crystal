import json
import time
from pathlib import Path
from threading import Lock

from app.domain.chat import ChatStorageError
from app.infrastructure.chat_documents import ChatDocuments
from app.infrastructure.chat_rooms import ChatRooms
from app.infrastructure.chat_store import ChatStore
from app.services.chat_files import ChatFiles, pdf_bytes
from app.services.chat_storage import ChatObjectStorage
from app.services.device_classification import classify_computer_name


def actor_info(session):
    sector = classify_computer_name(session["computer_name"]).get("sector")
    return {
        "key": session["windows_user"].casefold(),
        "windows_user": session["windows_user"],
        "name": session["operator_name"],
        "device": session["computer_name"],
        "sector": sector["code"] if sector else None,
    }


class ChatService:
    def __init__(self, settings, config):
        self.settings, self.config = settings, config
        self.store = ChatStore(config)
        self._presence = {}
        self._presence_lock = Lock()
        self.rooms = ChatRooms(self.store)
        self.documents = ChatDocuments(
            self.store,
            ChatFiles(
                lambda: config.comprovante_local()["sourceDir"],
                ChatObjectStorage(settings.backend_root, config),
            ),
        )
        rules = json.loads(
            (Path(__file__).parents[1] / "resources/device-naming.json").read_text(encoding="utf-8")
        )
        self.sectors = {
            item["code"]: item["label"] for item in rules["sector"] if item["code"] == "FIN"
        }

    def inbox(self, session):
        actor = actor_info(session)
        self.touch(actor)
        rows = self.rooms.inbox(actor)
        for row in rows:
            other = row["target"] if row["creator"] == actor["key"] else row["creator"]
            row["title"] = (
                (
                    self.sectors.get(row["target"], row["target"])
                    + " · "
                    + (row["creator_name"] or row["creator"])
                )
                if row["target_type"] == "sector"
                else (row["target_name"] if other == row["target"] else row["creator_name"])
                or other
            )
        latest = max(rows, key=lambda row: row["unread_seq"], default={})
        return {
            "rooms": rows,
            "unread": sum(row["unread"] for row in rows),
            "actor": actor,
            "latest_unread_seq": latest.get("unread_seq", 0),
            "latest_room": latest.get("title", ""),
        }

    def directory(self, session):
        actor = actor_info(session)
        self.touch(actor)
        return {
            "operators": [
                person
                for person in self.store.people()
                if person["key"] != actor["key"] and person["sector"] == "FIN" and person["online"]
            ],
            "sectors": [{"code": code, "name": name} for code, name in self.sectors.items()],
        }

    def create_room(self, session, body):
        actor = actor_info(session)
        self.touch(actor)
        return self.rooms.create(body, actor, self.sectors)

    def detail(self, session, identifier, before=None):
        actor = actor_info(session)
        with self.store.connection() as db:
            self.store.room(db, identifier, actor)
            messages = self.rooms.page(db, identifier, before)
            ids = [value["request_id"] for value in messages["messages"] if value.get("request_id")]
            rows = self.documents.rows(db, identifier, ids)
        warning = None
        pending = {row["cte"] for row in rows if row["publish_state"] == "pending"}
        for cte in pending:
            try:
                self.documents.publish(cte)
            except ChatStorageError as exc:
                warning = str(exc)
        if pending:
            with self.store.connection() as db:
                rows = self.documents.rows(db, identifier, ids)
        return {
            **messages,
            "requests": [self.documents.view(row) for row in rows],
            "delivery_warning": warning,
        }

    def touch(self, actor):
        signature = (actor["name"], actor["device"], actor["sector"])
        with self._presence_lock:
            previous = self._presence.get(actor["key"])
            if previous and previous[0] == signature and time.monotonic() - previous[1] < 30:
                return
            self.store.register(actor)
            self._presence[actor["key"]] = (signature, time.monotonic())

    def request(self, session, room, body):
        return self.documents.create(room, actor_info(session), body)

    def send(self, session, room, body):
        return self.rooms.send(room, actor_info(session), body)

    def read(self, session, room, through):
        self.rooms.read(room, actor_info(session), through)

    def claim(self, session, room, identifier):
        self.documents.claim(room, identifier, actor_info(session))

    def upload(self, session, room, identifier, kind, client_id, filename, data):
        actor = actor_info(session)
        with self.store.connection() as db:
            self.documents.get_request(db, room, identifier, actor)
        normalized = pdf_bytes(data, filename)
        self.documents.upload(room, identifier, actor, kind, client_id, filename, normalized)
        return self.detail(session, room)

    def download(self, session, room, identifier, kind):
        return self.documents.download(room, identifier, actor_info(session), kind)
