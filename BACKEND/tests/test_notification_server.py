import asyncio
import io
import signal
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import httpx
import psutil
import pytest
from botocore.exceptions import ClientError

from app.domain.hub_features import NotificationInput
from app.infrastructure.notifications import NotificationRepository
from app.infrastructure.operations_store import OperationsStore
from app.services import desktop_lifecycle
from app.services.notification_server import (
    NotificationDocument,
    NotificationFeed,
    NotificationServer,
)
from app.services.notifications import NotificationService


class FakeS3:
    def __init__(self):
        self.objects = {}
        self.modified = {}
        self.after_feed_put = None

    def put_object(self, *, Bucket, Key, Body, **kwargs):
        self.objects[Key] = Body
        self.modified[Key] = datetime.now(UTC)
        if Key.endswith("feed.json") and self.after_feed_put:
            callback, self.after_feed_put = self.after_feed_put, None
            callback()

    def get_object(self, *, Bucket, Key):
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        return {"Body": io.BytesIO(self.objects[Key])}

    def list_objects_v2(self, *, Bucket, Prefix, **kwargs):
        return {"Contents": [{"Key": key, "LastModified": self.modified[key]} for key in self.objects if key.startswith(Prefix)]}


@pytest.fixture
def system(tmp_path):
    store = OperationsStore(tmp_path / "operations.sqlite", "machine-1")
    store.initialize()
    client = FakeS3()
    config = SimpleNamespace(enabled=lambda: True, client=lambda: client)
    server = NotificationServer(config, prefix="test/notifications/")
    repository = NotificationRepository(store)
    service = NotificationService(repository, server)
    actor = {"windows_user": "DOMAIN\\developer", "operator_name": "Desenvolvedor"}
    yield SimpleNamespace(service=service, repository=repository, server=server, store=store,
                          client=client, actor=actor, config=config)
    store.close()


def test_publishing_uses_release_server_and_preserves_user_read_state(system):
    result = system.service.publish(NotificationInput(title="Aviso remoto", body="Comunicado para os operadores"), system.actor)
    assert "test/notifications/feed.json" in system.client.objects
    assert f"test/notifications/records/{result['id']}.json" in system.client.objects
    assert system.service.list(system.actor["windows_user"])[0]["read_at"]
    assert system.service.list("DOMAIN\\operator")[0]["read_at"] is None
    system.service.read(result["id"], "DOMAIN\\operator")
    read_at = system.service.list("DOMAIN\\operator")[0]["read_at"]
    system.service._checked_at = 0
    assert system.service.list("domain\\OPERATOR")[0]["read_at"] == read_at


def test_client_without_developer_credentials_reads_cached_feed_from_shared_database(system):
    system.service.publish(NotificationInput(title="Aviso disponível", body="Mensagem"), system.actor)
    config = SimpleNamespace(enabled=lambda: False, client=Mock(side_effect=AssertionError("write credentials used")))
    server = NotificationServer(config, transport=httpx.MockTransport(lambda request: httpx.Response(403)))
    other = NotificationService(NotificationRepository(system.store), server)
    assert other.list("DOMAIN\\operator")[0]["title"] == "Aviso disponível"
    config.client.assert_not_called()


def test_public_client_reads_remote_https_feed_and_caches_it(system):
    notice = NotificationDocument(id=uuid4(), title="Aviso público", body="Mensagem", author="Dev", created_at=datetime.now(UTC))
    feed = NotificationFeed(notifications=[notice])
    server = NotificationServer(SimpleNamespace(enabled=lambda: False),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=feed.model_dump(mode="json"))))
    service = NotificationService(system.repository, server)
    assert service.list("DOMAIN\\operator")[0]["id"] == str(notice.id)


def test_read_failure_without_cache_is_reported(system):
    server = NotificationServer(SimpleNamespace(enabled=lambda: False), transport=httpx.MockTransport(lambda request: httpx.Response(403)))
    with pytest.raises(ValueError, match="servidor de notificações"):
        NotificationService(system.repository, server).list("DOMAIN\\operator")


def test_archiving_remote_notice_updates_the_cache_and_history(system):
    result = system.service.publish(NotificationInput(title="Aviso encerrado", body="Mensagem"), system.actor)
    assert system.service.archive(result["id"])
    assert f"test/notifications/archived/{result['id']}.json" in system.client.objects
    assert system.service.list("DOMAIN\\operator") == []
    assert system.service.list(system.actor["windows_user"], developer=True)[0]["archived_at"]


def test_existing_notifications_can_move_to_server_without_losing_read_receipts(system):
    previous = system.repository.publish(NotificationInput(title="Aviso existente", body="Mensagem preservada"), system.actor)
    system.repository.read(previous["id"], "DOMAIN\\operator")
    assert system.service.migrate_existing(system.actor["windows_user"]) == 1
    assert system.service.list("DOMAIN\\operator")[0]["read_at"]
    assert system.server.read().notifications[0].id == UUID(previous["id"])


def test_concurrent_new_notice_is_included_when_reconciling_feed(system):
    first = NotificationDocument(id=uuid4(), title="Primeiro aviso", body="Mensagem", author="Dev", created_at=datetime.now(UTC))
    second = NotificationDocument(id=uuid4(), title="Segundo aviso", body="Mensagem", author="Dev", created_at=datetime.now(UTC))
    def concurrent_write():
        system.client.put_object(Bucket="test", Key=f"test/notifications/records/{second.id}.json", Body=second.model_dump_json().encode())
    system.client.after_feed_put = concurrent_write
    result = system.server.publish([first])
    assert {value.id for value in result.notifications} == {first.id, second.id}
    assert len(system.server.read().notifications) == 2


def test_developer_gate_and_expiration_validation(system):
    system.config.enabled = lambda: False
    with pytest.raises(PermissionError):
        system.service.publish(NotificationInput(title="Aviso bloqueado", body="Mensagem"), system.actor)
    system.config.enabled = lambda: True
    with pytest.raises(ValueError, match="futura"):
        system.service.publish(NotificationInput(title="Aviso expirado", body="Mensagem", expires_at=datetime.now(UTC) - timedelta(days=1)), system.actor)


def test_desktop_exit_requests_uvicorn_shutdown_and_parent_pid_reuse_is_detected(monkeypatch):
    kill = Mock()
    monkeypatch.setattr(desktop_lifecycle.signal, "raise_signal", kill)
    monkeypatch.setattr(desktop_lifecycle.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(desktop_lifecycle.psutil, "Process", lambda pid: SimpleNamespace(create_time=lambda: 200, is_running=lambda: True))
    asyncio.run(desktop_lifecycle.watch_desktop(123, 100))
    kill.assert_called_once_with(signal.SIGTERM)


def test_lifecycle_monitor_is_absent_for_standalone_backend(monkeypatch):
    monkeypatch.delenv("NOVELIS_DESKTOP_PARENT_PID", raising=False)
    monkeypatch.delenv("NOVELIS_DESKTOP_PARENT_CREATED_AT", raising=False)
    assert desktop_lifecycle.monitor_desktop() is None


def test_disappeared_desktop_is_detected(monkeypatch):
    monkeypatch.setattr(desktop_lifecycle.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(desktop_lifecycle.psutil, "Process", Mock(side_effect=psutil.NoSuchProcess(123)))
    kill = Mock()
    monkeypatch.setattr(desktop_lifecycle.signal, "raise_signal", kill)
    asyncio.run(desktop_lifecycle.watch_desktop(123, 100))
    kill.assert_called_once()
