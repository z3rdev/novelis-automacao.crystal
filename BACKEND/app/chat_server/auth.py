import hashlib
import hmac
import json
from base64 import urlsafe_b64decode
from pathlib import Path

from fastapi import HTTPException, Request


class ClientRegistry:
    def __init__(self, path):
        self.path = Path(path)

    def authenticate(self, client_id, token, windows_user, computer_name):
        records = json.loads(self.path.read_text(encoding="utf-8-sig")).get("clients", [])
        record = next(
            (value for value in records if value["id"] == client_id and value.get("enabled", True)),
            None,
        )
        digest = hashlib.sha256(str(token).encode()).hexdigest()
        if not record or not hmac.compare_digest(record["token_sha256"], digest):
            raise HTTPException(401, "Identificação do dispositivo recusada.")
        if record["computer_name"].casefold() != str(computer_name).casefold() or str(
            windows_user
        ).casefold() not in [name.casefold() for name in record["windows_users"]]:
            raise HTTPException(403, "A conta Windows não está autorizada neste dispositivo.")
        return {
            "windows_user": windows_user,
            "computer_name": record["computer_name"],
            "operator_name": windows_user.rsplit("\\", 1)[-1],
        }

    def from_headers(self, headers):
        scheme, _, token = headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer":
            raise HTTPException(401, "Autenticação do dispositivo necessária.")
        try:
            identity = json.loads(urlsafe_b64decode(headers.get("x-chat-identity", "")))
            return self.authenticate(
                headers.get("x-chat-client", ""),
                token,
                identity["windows_user"],
                identity["computer_name"],
            )
        except (ValueError, KeyError, TypeError):
            raise HTTPException(401, "Identificação do operador inválida.") from None


async def central_actor(request: Request):
    return request.app.state.chat_registry.from_headers(request.headers)
