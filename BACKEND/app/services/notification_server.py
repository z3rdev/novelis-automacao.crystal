import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

import httpx
from pydantic import BaseModel, Field, field_validator

from app.domain.hub_features import NotificationInput
from app.services.releases.config import BUCKET, ENDPOINT, PREFIX, DeveloperConfig
from app.services.releases.storage import storage_error

MAX_FEED_BYTES = 10 * 1024**2


class NotificationDocument(NotificationInput):
    id: UUID
    author: str = Field(min_length=1, max_length=150)
    created_at: datetime
    archived_at: datetime | None = None

    @field_validator("created_at", "archived_at")
    @classmethod
    def aware_timestamp(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("O aviso precisa identificar o fuso horário.")
        return value.astimezone(UTC) if value else None


class NotificationFeed(BaseModel):
    schema_version: int = Field(default=1, ge=1, le=1)
    notifications: list[NotificationDocument] = Field(default_factory=list, max_length=200)


def encode_feed(feed: NotificationFeed) -> bytes:
    return json.dumps(feed.model_dump(mode="json"), ensure_ascii=False, sort_keys=True).encode("utf-8")


class NotificationServer:
    def __init__(self, config: DeveloperConfig, prefix: str = PREFIX + "notifications/", transport=None):
        self.config, self.prefix, self.transport = config, prefix, transport

    @property
    def url(self) -> str:
        return f"{ENDPOINT}/{BUCKET}/{self.prefix}feed.json"

    def read(self) -> NotificationFeed:
        if self.config.enabled():
            from botocore.exceptions import BotoCoreError, ClientError
            try:
                response = self.config.client().get_object(Bucket=BUCKET, Key=self.prefix + "feed.json")
                with response["Body"] as body:
                    content = body.read(MAX_FEED_BYTES + 1)
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") in {"NoSuchKey", "NoSuchObject", "404"}:
                    return NotificationFeed()
                raise storage_error(exc) from None
            except BotoCoreError as exc:
                raise storage_error(exc) from None
        else:
            with (
                httpx.Client(timeout=12, transport=self.transport, follow_redirects=False) as client,
                client.stream("GET", self.url, headers={"Cache-Control": "no-cache"}) as response,
            ):
                if response.status_code == 404:
                    return NotificationFeed()
                response.raise_for_status()
                content = bytearray()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_FEED_BYTES:
                        raise ValueError("O feed de notificações excede o tamanho permitido.")
        if len(content) > MAX_FEED_BYTES:
            raise ValueError("O feed de notificações excede o tamanho permitido.")
        return NotificationFeed.model_validate_json(content)

    def _objects(self, client, folder: str) -> list[dict]:
        objects, continuation = [], {}
        while True:
            response = client.list_objects_v2(Bucket=BUCKET, Prefix=self.prefix + folder, **continuation)
            objects.extend(response.get("Contents", []))
            if len(objects) > 10000:
                raise ValueError("O catálogo de notificações precisa ser compactado pelo administrador.")
            if not response.get("IsTruncated"):
                return objects
            continuation = {"ContinuationToken": response["NextContinuationToken"]}

    def _catalog(self, client) -> NotificationFeed:
        rows = []
        records = sorted(self._objects(client, "records/"), key=lambda item: item["LastModified"], reverse=True)
        archived = {entry["Key"].rsplit("/", 1)[-1].removesuffix(".json"): entry["LastModified"] for entry in self._objects(client, "archived/")}
        for entry in records[:200]:
            name = entry["Key"].rsplit("/", 1)[-1].removesuffix(".json")
            try:
                identifier = UUID(name)
            except ValueError:
                continue
            response = client.get_object(Bucket=BUCKET, Key=entry["Key"])
            with response["Body"] as body:
                content = body.read(65537)
            if len(content) > 65536:
                raise ValueError("O aviso excede o tamanho permitido.")
            notice = NotificationDocument.model_validate_json(content)
            if notice.id != identifier:
                raise ValueError("O aviso difere de sua identificação no servidor.")
            if name in archived and notice.archived_at is None:
                notice.archived_at = archived[name]
            rows.append(notice)
        rows.sort(key=lambda value: value.created_at, reverse=True)
        return NotificationFeed(notifications=rows)

    def _commit(self, client) -> NotificationFeed:
        for _ in range(3):
            if not self.config.enabled():
                raise PermissionError("Modo desenvolvedor desativado.")
            feed = self._catalog(client)
            encoded = encode_feed(feed)
            client.put_object(Bucket=BUCKET, Key=self.prefix + "feed.json", Body=encoded,
                              ContentType="application/json", CacheControl="no-cache")
            if hashlib.sha256(encoded).digest() == hashlib.sha256(encode_feed(self._catalog(client))).digest():
                return feed
        raise ValueError("Outros avisos foram publicados simultaneamente. Consulte a central e tente novamente.")

    def publish(self, notices: list[NotificationDocument]) -> NotificationFeed:
        from botocore.exceptions import BotoCoreError, ClientError
        try:
            client = self.config.client()
            for notice in notices:
                if not self.config.enabled():
                    raise PermissionError("Modo desenvolvedor desativado.")
                client.put_object(Bucket=BUCKET, Key=self.prefix + f"records/{notice.id}.json",
                    Body=notice.model_dump_json().encode("utf-8"), ContentType="application/json")
                if notice.archived_at:
                    client.put_object(Bucket=BUCKET, Key=self.prefix + f"archived/{notice.id}.json",
                        Body=json.dumps({"archived_at": notice.archived_at.isoformat()}).encode("utf-8"), ContentType="application/json")
            return self._commit(client)
        except (BotoCoreError, ClientError) as exc:
            raise storage_error(exc) from None

    def archive(self, identifier: str) -> NotificationFeed:
        from botocore.exceptions import BotoCoreError, ClientError
        try:
            client = self.config.client()
            client.put_object(Bucket=BUCKET, Key=self.prefix + f"archived/{UUID(identifier)}.json",
                Body=json.dumps({"archived_at": datetime.now(UTC).isoformat()}).encode("utf-8"), ContentType="application/json")
            return self._commit(client)
        except (BotoCoreError, ClientError) as exc:
            raise storage_error(exc) from None
