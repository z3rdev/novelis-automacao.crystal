"""Authenticated central-chat adapter using the trusted local Windows session."""

import json
import os
from base64 import urlsafe_b64encode
from pathlib import Path
from threading import Lock
from urllib.parse import urlsplit

import httpx

from app.domain.chat import ChatError, ChatStorageError


class RemoteChat:
    def __init__(self, root, config):
        self.root, self.config = root, config
        self._client = None
        self._client_lock = Lock()

    def client(self):
        with self._client_lock:
            if self._client is None:
                self._client = httpx.Client(
                    timeout=httpx.Timeout(90, connect=8),
                    limits=httpx.Limits(
                        max_connections=12, max_keepalive_connections=6, keepalive_expiry=60
                    ),
                    follow_redirects=False,
                )
            return self._client

    def close(self):
        with self._client_lock:
            if self._client is not None:
                self._client.close()
                self._client = None

    def profile(self):
        value = os.environ.get("CHAT_SERVER_CONFIG_FILE") or self.config.get(
            "CHAT_SERVER_CONFIG_FILE"
        )
        if not value:
            return None
        path = Path(value)
        try:
            profile = json.loads(
                (path if path.is_absolute() else self.root / path).read_text(encoding="utf-8-sig")
            )
            url = urlsplit(profile["url"])
            if (
                url.scheme != "https"
                and not (url.scheme == "http" and url.hostname in {"127.0.0.1", "localhost"})
                or url.username
                or url.password
                or url.query
                or url.fragment
                or not profile.get("client_id")
                or not profile.get("token")
            ):
                raise ValueError("profile")
            profile["url"] = profile["url"].rstrip("/")
            return profile
        except (OSError, ValueError, KeyError, TypeError):
            raise ChatStorageError("Confira o perfil privado do servidor de mensagens.") from None

    def headers(self, actor):
        profile = self.profile()
        identity = {key: actor[key] for key in ("windows_user", "computer_name")}
        return {
            "Authorization": "Bearer " + profile["token"],
            "X-Chat-Client": profile["client_id"],
            "X-Chat-Identity": urlsafe_b64encode(json.dumps(identity).encode()).decode(),
        }

    def websocket_auth(self, actor):
        profile = self.profile()
        return {
            "client_id": profile["client_id"],
            "token": profile["token"],
            "windows_user": actor["windows_user"],
            "computer_name": actor["computer_name"],
        }

    def _request(self, actor, method, path, *, body=None, content=None, params=None, binary=False):
        try:
            profile = self.profile()
            response = self.client().request(
                method,
                profile["url"] + "/api/hub/chat" + path,
                headers=self.headers(actor),
                json=body,
                content=content,
                params=params,
            )
            if response.is_error:
                error = ChatError("O servidor de mensagens recusou a operação.")
                error.status_code = (
                    response.status_code
                    if response.status_code in {401, 403, 404, 409, 413, 422, 503}
                    else 503
                )
                try:
                    detail = response.json().get("detail")
                    if isinstance(detail, str):
                        error.args = (detail,)
                except ValueError:
                    pass
                raise error
            if binary:
                return response.content
            return None if response.status_code == 204 else response.json()
        except httpx.HTTPError:
            raise ChatStorageError(
                "O servidor central de mensagens está indisponível. Tentando reconectar."
            ) from None

    def inbox(self, actor):
        return self._request(actor, "GET", "")

    def directory(self, actor):
        return self._request(actor, "GET", "/directory")

    def create_room(self, actor, body):
        return self._request(actor, "POST", "/rooms", body=body.model_dump(mode="json"))

    def detail(self, actor, room, before=None):
        return self._request(
            actor, "GET", f"/rooms/{room}", params={"before": before} if before else None
        )

    def send(self, actor, room, body):
        return self._request(
            actor, "POST", f"/rooms/{room}/messages", body=body.model_dump(mode="json")
        )

    def read(self, actor, room, through):
        return self._request(actor, "POST", f"/rooms/{room}/read", body={"through": through})

    def request(self, actor, room, body):
        return self._request(
            actor, "POST", f"/rooms/{room}/requests", body=body.model_dump(mode="json")
        )

    def claim(self, actor, room, identifier):
        return self._request(actor, "POST", f"/rooms/{room}/requests/{identifier}/claim")

    def upload(self, actor, room, identifier, kind, client_id, filename, data):
        return self._request(
            actor,
            "PUT",
            f"/rooms/{room}/requests/{identifier}/files/{kind}",
            content=data,
            params={"client_id": str(client_id), "filename": filename},
        )

    def download(self, actor, room, identifier, kind):
        data = self._request(
            actor, "GET", f"/rooms/{room}/requests/{identifier}/files/{kind}", binary=True
        )
        return data, f"GNRE_{identifier}_{kind}.pdf"
