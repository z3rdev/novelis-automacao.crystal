import asyncio
import logging
import sqlite3
import threading
import time
from datetime import UTC, datetime
from uuid import uuid4

import httpx
from pydantic import ValidationError

from app.services.notification_server import NotificationDocument, NotificationFeed

logger = logging.getLogger(__name__)
CACHE_NAME = "hub-notification-server-feed"


class NotificationService:
    def __init__(self, repository, server):
        self.repository, self.server, self.store = repository, server, repository.store
        self._lock = threading.RLock()
        self._checked_at = 0.0

    def _save_cache(self, feed: NotificationFeed) -> None:
        values = [item.model_dump(mode="json") for item in feed.notifications]
        self.repository.synchronize(values)
        self.store.snapshot(CACHE_NAME, feed.model_dump(mode="json"))
        self._checked_at = time.monotonic()

    def refresh(self) -> None:
        with self._lock:
            if time.monotonic() - self._checked_at < 20:
                return
            try:
                self._save_cache(self.server.read())
            except (OSError, ValueError, httpx.HTTPError):
                cached = self.store.snapshot(CACHE_NAME)
                if cached is None:
                    raise ValueError("O servidor de notificações está indisponível. Verifique o acesso ao MinIO.") from None
                self.repository.synchronize([item.model_dump(mode="json") for item in NotificationFeed.model_validate(cached).notifications])
                self._checked_at = time.monotonic()
                logger.debug("Notificações carregadas do cache compartilhado enquanto o servidor está indisponível.")

    def list(self, windows_user: str, *, developer=False) -> list[dict]:
        self.refresh()
        feed = NotificationFeed.model_validate(self.store.snapshot(CACHE_NAME) or {})
        identifiers = {str(value.id) for value in feed.notifications}
        return [row for row in self.repository.list(windows_user, developer=developer) if row["id"] in identifiers]

    def publish(self, body, actor: dict) -> dict:
        if not self.server.config.enabled():
            raise PermissionError("Modo desenvolvedor desativado.")
        if body.expires_at and body.expires_at <= datetime.now(UTC):
            raise ValueError("A expiração precisa ser futura.")
        notice = NotificationDocument(**body.model_dump(), id=uuid4(), author=actor["operator_name"], created_at=datetime.now(UTC))
        with self._lock:
            try:
                feed = self.server.publish([notice])
            except ValidationError:
                raise ValueError("O catálogo de notificações do servidor possui formato inválido.") from None
            self._save_cache(feed)
            self.repository.read(str(notice.id), actor["windows_user"])
        return notice.model_dump(mode="json")

    def read(self, identifier: str, windows_user: str) -> bool:
        return self.repository.read(identifier, windows_user)

    def archive(self, identifier: str) -> bool:
        if not self.server.config.enabled():
            raise PermissionError("Modo desenvolvedor desativado.")
        with self._lock:
            if not any(item["id"] == identifier for item in self.repository.list("", developer=True)):
                return False
            self._save_cache(self.server.archive(identifier))
        return True

    def migrate_existing(self, windows_user: str) -> int:
        with self._lock:
            rows = self.repository.list(windows_user, developer=True)
            notices = [NotificationDocument.model_validate(row) for row in rows]
            if notices:
                self._save_cache(self.server.publish(notices))
            return len(notices)

    async def sync_loop(self) -> None:
        while True:
            try:
                await asyncio.to_thread(self.refresh)
            except (OSError, RuntimeError, ValueError, sqlite3.Error):
                logger.debug("Aguardando disponibilidade do servidor de notificações e do cache compartilhado.")
            await asyncio.sleep(20)
