import hashlib
import json
from base64 import urlsafe_b64encode
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from test_chat_postgres import chat, create  # noqa: F401 - shared isolated PostgreSQL fixture

from app.chat_server.auth import ClientRegistry
from app.chat_server.main import create_server

pytestmark = pytest.mark.skipif(
    __import__("os").getenv("NOVELIS_CHAT_PG_TEST") != "1",
    reason="Isolated PostgreSQL test is opt-in",
)


def test_websocket_authentication_delivery_idempotency_and_room_permissions(chat, tmp_path):  # noqa: F811
    owner, financial, room = create(chat)
    path = tmp_path / "clients.json"
    clients = [
        {
            "id": name,
            "token_sha256": hashlib.sha256((name + "-test-token").encode()).hexdigest(),
            "computer_name": actor["computer_name"],
            "windows_users": [actor["windows_user"]],
        }
        for name, actor in (("owner", owner), ("finance", financial))
    ]
    path.write_text(json.dumps({"clients": clients}))
    registry = ClientRegistry(path)
    app = create_server(SimpleNamespace(), chat, registry)
    auth = {
        "client_id": "owner",
        "token": "owner-test-token",
        **{key: owner[key] for key in ("windows_user", "computer_name")},
    }
    with TestClient(app) as client:
        assert client.get("/api/hub/chat").status_code == 401
        with client.websocket_connect("/api/hub/chat/live") as invalid:
            invalid.send_json({**auth, "token": "invalid"})
            with pytest.raises(WebSocketDisconnect):
                invalid.receive_json()
        with (
            client.websocket_connect("/api/hub/chat/live") as socket,
            client.websocket_connect("/api/hub/chat/live") as receiver,
        ):
            socket.send_json(auth)
            assert socket.receive_json()["type"] == "chat.changed"
            assert socket.receive_json()["type"] == "ping"
            receiver.send_json(
                {
                    "client_id": "finance",
                    "token": "finance-test-token",
                    **{key: financial[key] for key in ("windows_user", "computer_name")},
                }
            )
            assert receiver.receive_json()["type"] == "chat.changed"
            assert receiver.receive_json()["type"] == "ping"
            message_id = str(uuid4())
            command = {
                "type": "message.send",
                "room_id": room,
                "client_id": message_id,
                "body": "Mensagem de controle via WebSocket",
            }

            def ack():
                for _ in range(8):
                    value = socket.receive_json()
                    if value["type"] == "message.ack":
                        return value
                raise AssertionError("No acknowledgement")

            socket.send_json(command)
            first = ack()
            for _ in range(8):
                event = receiver.receive_json()
                if event["type"] == "message.created":
                    break
            assert event["message"]["id"] == first["message"]["id"]
            assert event["room_id"] == room
            socket.send_json(command)
            assert ack()["message"]["id"] == first["message"]["id"]
            identity = {key: financial[key] for key in ("windows_user", "computer_name")}
            headers = {
                "Authorization": "Bearer finance-test-token",
                "X-Chat-Client": "finance",
                "X-Chat-Identity": urlsafe_b64encode(json.dumps(identity).encode()).decode(),
            }
            sent_http = client.post(
                f"/api/hub/chat/rooms/{room}/messages",
                headers=headers,
                json={"client_id": str(uuid4()), "body": "Mensagem HTTP com entrega WebSocket"},
            )
            assert sent_http.status_code == 201
            for _ in range(10):
                event = receiver.receive_json()
                if event.get("message", {}).get("id") == sent_http.json()["id"]:
                    break
            assert event["type"] == "message.created"
            assert event["message"]["id"] == sent_http.json()["id"]
            detail = client.get(f"/api/hub/chat/rooms/{room}", headers=headers)
            assert detail.status_code == 200, detail.text
            assert sum(value["client_id"] == message_id for value in detail.json()["messages"]) == 1
            headers["X-Chat-Identity"] = urlsafe_b64encode(
                json.dumps({**identity, "computer_name": "OTHER"}).encode()
            ).decode()
            assert client.get("/api/hub/chat", headers=headers).status_code == 403
