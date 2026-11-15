import io
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from chat_storage_fake import MemoryS3
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter

from app.api.routers.chat import router
from app.config.legacy_config import LegacyConfig
from app.config.settings import Settings
from app.domain.chat import (
    ChatMessageInput,
    ChatError,
    ChatNotFound,
    ChatStorageError,
    ConversationInput,
    GnreRequestInput,
)
from app.infrastructure.chamados_postgres import ChamadosPostgres
from app.services.chat import ChatService
from app.services.chat_files import published_documents
from app.services.chat_storage import ChatObjectStorage

pytestmark = pytest.mark.skipif(
    os.getenv("NOVELIS_CHAT_PG_TEST") != "1", reason="Isolated PostgreSQL test is opt-in"
)


@pytest.fixture(scope="module")
def chat(tmp_path_factory):
    from psycopg import sql

    settings = Settings()
    config = LegacyConfig(settings)
    config.values["COMPROVANTE_SOURCE_DIR"] = str(tmp_path_factory.mktemp("chat-documents"))
    service = ChatService(settings, config)
    service.documents.files.objects = ChatObjectStorage(settings.backend_root, config, MemoryS3())
    database, prefix = ChamadosPostgres(config), "qa_chat_" + uuid4().hex + "_"

    class Isolated:
        enabled = True

        @contextmanager
        def connection(self):
            with database.connection() as db:

                class Proxy:
                    def execute(self, statement, params=None):
                        return db.execute(
                            statement.replace("cargo_hub_chat_", prefix).replace(
                                "ix_chat_", prefix + "ix_"
                            ),
                            params,
                        )

                    def rollback(self):
                        db.rollback()

                yield Proxy()

    service.store.db = Isolated()
    service.store.ensure()
    try:
        yield service
    finally:
        with database.connection() as db:
            for suffix in ("reads", "messages", "requests", "documents", "rooms", "people"):
                db.execute(
                    sql.SQL("DROP TABLE IF EXISTS public.{}").format(
                        sql.Identifier(prefix + suffix)
                    )
                )


def actor(name, computer="NB-TI-VIN-01"):
    return {"windows_user": "QA\\" + name, "operator_name": name, "computer_name": computer}


def sample_pdf(width):
    writer, stream = PdfWriter(), io.BytesIO()
    writer.add_blank_page(width=width, height=100)
    writer.write(stream)
    return stream.getvalue()


def create(chat):
    owner, financial = actor(uuid4().hex[:10]), actor(uuid4().hex[:10], "NB-FIN-VIN-01")
    chat.inbox(owner)
    chat.inbox(financial)
    room = chat.create_room(owner, ConversationInput(target_type="sector", target="FIN"))["id"]
    return owner, financial, room


def test_sector_visibility_idempotent_messages_and_read_receipts(chat):
    owner, financial, room = create(chat)
    message = ChatMessageInput(client_id=uuid4(), body="Preciso de uma guia")
    first = chat.send(owner, room, message)
    assert chat.send(owner, room, message)["id"] == first["id"]
    inbox = chat.inbox(financial)
    item = next(row for row in inbox["rooms"] if row["id"] == room)
    assert item["unread"] == 1
    with pytest.raises(ChatNotFound):
        chat.detail(actor("other", "NB-MAN-VIN-01"), room)
    chat.read(financial, room, first["seq"])
    assert next(row for row in chat.inbox(financial)["rooms"] if row["id"] == room)["unread"] == 0
    directory = chat.directory(owner)
    assert directory["sectors"] == [{"code": "FIN", "name": "Financeiro"}]
    assert any(person["key"] == financial["windows_user"].casefold() for person in directory["operators"])
    assert all(person["sector"] == "FIN" and person["online"] for person in directory["operators"])
    with chat.store.connection() as db:
        db.execute("UPDATE public.cargo_hub_chat_people SET seen_at=now()-interval '2 minutes' WHERE user_key=%s", (financial["windows_user"].casefold(),))
    assert not any(person["key"] == financial["windows_user"].casefold() for person in chat.directory(owner)["operators"])
    with pytest.raises(ChatError, match="online do Financeiro"):
        chat.create_room(owner, ConversationInput(target_type="operator", target=financial["windows_user"].casefold()))


def test_parallel_files_publish_a_single_coherent_bundle(chat):
    owner, financial, room = create(chat)
    request = chat.request(
        owner, room, GnreRequestInput(cte="10-10-2789", chamado="20261114580001")
    )

    def upload(kind):
        return chat.upload(
            financial,
            room,
            request["id"],
            kind,
            uuid4(),
            f"{kind}.pdf",
            sample_pdf(100 if kind == "guia" else 200),
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(upload, ("guia", "comprovante")))
    value = chat.detail(owner, room)["requests"][0]
    assert value["state"] == "available"
    combined, name = chat.download(owner, room, request["id"], "combined")
    assert name == "GNR_CMP_10-10-2789.pdf"
    assert [page.mediabox.width for page in PdfReader(io.BytesIO(combined)).pages] == [100, 200]
    paths = published_documents(chat.documents.files.root, "10-10-2789")
    assert set(paths) == {"guia", "comprovante", "combined"}
    assert chat.request(owner, room, GnreRequestInput(cte="10-10-2789"))["id"] == request["id"]


def test_failed_share_publication_remains_recoverable(chat, monkeypatch):
    owner, financial, room = create(chat)
    request = chat.request(owner, room, GnreRequestInput(cte="8-10-1559"))
    publish = chat.documents.files.publish

    def unavailable(_):
        raise ChatStorageError("Share unavailable for controlled test")

    monkeypatch.setattr(chat.documents.files, "publish", unavailable)
    with pytest.raises(ChatStorageError):
        chat.upload(financial, room, request["id"], "guia", uuid4(), "guia.pdf", sample_pdf(100))
    detail = chat.detail(owner, room)
    assert detail["requests"][0]["state"] == "publishing"
    assert detail["delivery_warning"] == "Share unavailable for controlled test"
    monkeypatch.setattr(chat.documents.files, "publish", publish)
    assert chat.detail(owner, room)["requests"][0]["state"] == "partial"


def test_api_session_authorization_and_invalid_upload(chat):
    owner, _financial, room = create(chat)
    app = FastAPI()
    app.state.chat = chat
    app.state.session_audit = SimpleNamespace(
        session=lambda token: owner if token == "operator" else None
    )
    app.include_router(router)
    with TestClient(app) as client:
        assert client.get("/hub/chat").status_code == 401
        headers = {"X-Operator-Session": "operator"}
        assert client.get("/hub/chat", headers=headers).status_code == 200
        assert (
            client.post(
                f"/hub/chat/rooms/{room}/requests", headers=headers, json={"cte": "../outside"}
            ).status_code
            == 422
        )
        request = chat.request(owner, room, GnreRequestInput(cte="1-10-888"))
        response = client.put(
            f"/hub/chat/rooms/{room}/requests/{request['id']}/files/guia",
            headers=headers,
            params={"client_id": str(uuid4()), "filename": "bad.pdf"},
            content=b"invalid",
        )
        assert response.status_code == 422


def test_confirmed_ticket_archives_documents_then_cleans_network_and_expires(chat):
    from datetime import UTC, datetime

    from app.services.chat_archive import ChatArchive
    from app.services.chat_storage import ARCHIVE, PENDING

    owner, financial, room = create(chat)
    cte = "11-10-433"
    request = chat.request(owner, room, GnreRequestInput(cte=cte))
    for kind in ("guia", "comprovante"):
        chat.upload(financial, room, request["id"], kind, uuid4(), kind + ".pdf", sample_pdf(100))
    directory = chat.documents.files.directory(cte)
    assert {path.name for path in directory.iterdir()} == {
        "GNR_CMP_11-10-433.pdf",
        ".cargo-hub-documents.json",
    }
    archive = ChatArchive(chat, None)
    event = {
        "kind": "novelis.save",
        "created_at": datetime.now(UTC).isoformat(),
        "payload": {"cte": cte, "number": "999999999", "result": {"ok": True}},
    }
    archive.confirm({**event, "payload": {**event["payload"], "result": {"ok": False}}})
    assert directory.exists()
    archive.confirm(event)
    remote = chat.documents.files.objects.client()
    remote.fail_copy = True
    with pytest.raises(ChatStorageError, match="arquivamento"):
        archive.finalize(cte)
    assert (directory / "GNR_CMP_11-10-433.pdf").is_file()
    remote.fail_copy = False
    archive.finalize(cte)
    assert not directory.exists()
    value = chat.detail(owner, room)["requests"][0]
    assert value["state"] == "archived"
    assert value["expires_at"]
    assert (
        len(PdfReader(io.BytesIO(chat.download(owner, room, request["id"], "combined")[0])).pages)
        == 2
    )
    assert not any(key.startswith(PENDING + cte + "/") for key in remote.data)
    assert len([key for key in remote.data if key.startswith(ARCHIVE + cte + "/")]) == 3
    archive.expire(cte)
    assert any(key.startswith(ARCHIVE + cte + "/") for key in remote.data)
    with chat.store.connection() as db:
        db.execute(
            "UPDATE public.cargo_hub_chat_documents SET expires_at=now()-interval '1 second' WHERE cte=%s",
            (cte,),
        )
    archive.expire(cte)
    assert not any(key.startswith(ARCHIVE + cte + "/") for key in remote.data)
    assert chat.detail(owner, room)["requests"][0]["state"] == "expired"
    with pytest.raises(ChatStorageError, match="30 dias"):
        chat.download(owner, room, request["id"], "combined")


def test_legacy_network_bundle_is_migrated_to_minio_without_losing_documents(chat):
    from datetime import UTC, datetime
    from hashlib import sha256

    from psycopg.types.json import Jsonb

    from app.services.chat_archive import ChatArchive
    from app.services.chat_files import ChatFiles, merge_pdfs

    owner, _, room = create(chat)
    cte = "8-10-1999"
    chat.request(owner, room, GnreRequestInput(cte=cte))
    legacy = ChatFiles(chat.documents.files.root)
    data = sample_pdf(100)
    row = {"cte": cte, "generation": uuid4()}
    for kind, content in (
        ("guia", data),
        ("comprovante", data),
        ("combined", merge_pdfs(data, data)),
    ):
        metadata = {
            "id": str(uuid4()),
            "kind": kind,
            "sha256": sha256(content).hexdigest(),
            "uploaded_at": datetime.now(UTC).isoformat(),
        }
        legacy.write(cte, metadata, content)
        row[kind] = metadata
    legacy.publish(row)
    with chat.store.connection() as db:
        db.execute(
            "UPDATE public.cargo_hub_chat_documents SET guia=%s,comprovante=%s,combined=%s,generation=%s WHERE cte=%s",
            (
                Jsonb(row["guia"]),
                Jsonb(row["comprovante"]),
                Jsonb(row["combined"]),
                row["generation"],
                cte,
            ),
        )
    ChatArchive(chat, None).migrate(cte)
    value = chat.detail(owner, room)["requests"][0]
    assert value["state"] == "available"
    assert all(value[kind]["object_key"] for kind in ("guia", "comprovante", "combined"))
    assert {path.name for path in legacy.directory(cte).iterdir()} == {
        f"GNR_CMP_{cte}.pdf",
        ".cargo-hub-documents.json",
    }


def test_maintenance_replays_confirmation_even_after_many_other_events(chat, tmp_path):
    import json
    from datetime import UTC, datetime

    from app.infrastructure.operations_store import OperationsStore
    from app.services.chat_archive import ChatArchive

    owner, financial, room = create(chat)
    cte = "11-10-434"
    request = chat.request(owner, room, GnreRequestInput(cte=cte))
    for kind in ("guia", "comprovante"):
        chat.upload(financial, room, request["id"], kind, uuid4(), "qa.pdf", sample_pdf(100))
    operations = OperationsStore(tmp_path / "operations.sqlite", "another-computer")
    operations.initialize()
    operations.add_event(
        {
            "kind": "novelis.save",
            "created_at": datetime.now(UTC).isoformat(),
            "payload": {"cte": cte, "number": "20261115999999", "result": {"ok": True}},
        }
    )
    with operations.connection() as db:
        db.executemany(
            "INSERT INTO execution_events(run_id,payload) VALUES (?,?)",
            [(None, json.dumps({"kind": "qa.other", "payload": {}})) for _ in range(1001)],
        )
    assert not any(
        event.get("kind") == "novelis.save"
        for event in operations.events(limit=1000, all_machines=True)
    )
    archive = ChatArchive(chat, operations)
    archive.tick()
    assert chat.detail(owner, room)["requests"][0]["state"] == "archived"
    assert not chat.documents.files.directory(cte).exists()
    assert archive.retention_ready is True
    operations.close()
