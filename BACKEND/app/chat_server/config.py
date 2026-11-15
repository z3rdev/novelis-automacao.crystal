import json
import os
from pathlib import Path


class ServerConfig:
    def __init__(self, path=None):
        path = Path(path or os.environ.get("CHAT_SERVER_SETTINGS", "/run/secrets/chat-settings"))
        self.values = json.loads(path.read_text(encoding="utf-8-sig"))
        if not self.get("CHAMADOS_PG_HOST"):
            raise ValueError("Configure o PostgreSQL do servidor de chat.")

    def get(self, key, default=""):
        return str(self.values.get(key, default))

    def comprovante_local(self):
        return {"sourceDir": "/tmp/cargo-hub-chat"}
