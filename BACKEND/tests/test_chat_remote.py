import json
from types import SimpleNamespace

import httpx
import pytest

from app.domain.chat import ChatStorageError, ConversationInput, GnreRequestInput
from app.services.chat_remote import RemoteChat


def test_remote_chat_uses_private_profile_and_preserves_actor(tmp_path, monkeypatch):
    profile = tmp_path / "chat.json"
    profile.write_text(
        json.dumps(
            {"url": "https://chat.example.test", "client_id": "device", "token": "private-fixture"}
        )
    )
    gateway = RemoteChat(tmp_path, SimpleNamespace(get=lambda key: "chat.json"))
    actor = {"windows_user": "EXAMPLE\\operator", "computer_name": "NB-FIN-VIN-01"}
    captured = []

    def handle(request):
        captured.append(request)
        return httpx.Response(200, json={"id": "room"})

    client_type = httpx.Client
    monkeypatch.setattr(
        "app.services.chat_remote.httpx.Client",
        lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs),
    )
    assert (
        gateway.create_room(actor, ConversationInput(target_type="sector", target="FIN"))["id"]
        == "room"
    )
    gateway.request(actor, "room", GnreRequestInput(cte="11-10-433"))
    persistent_client = gateway.client()
    assert gateway.client() is persistent_client
    assert captured[0].headers["authorization"] == "Bearer private-fixture"
    assert captured[0].url.path == "/api/hub/chat/rooms"
    assert captured[1].url.path == "/api/hub/chat/rooms/room/requests"
    assert gateway.websocket_auth(actor)["windows_user"] == actor["windows_user"]
    gateway.close()
    assert persistent_client.is_closed


def test_remote_chat_rejects_unencrypted_public_endpoint(tmp_path):
    (tmp_path / "chat.json").write_text(
        json.dumps({"url": "http://69.62.97.245", "client_id": "device", "token": "fixture"})
    )
    with pytest.raises(ChatStorageError, match="perfil privado"):
        RemoteChat(tmp_path, SimpleNamespace(get=lambda key: "chat.json")).profile()
