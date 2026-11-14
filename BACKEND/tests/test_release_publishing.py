import asyncio
import hashlib
import io
import json
import struct
import time
from types import SimpleNamespace

import httpx
import pytest
from botocore.exceptions import ClientError
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers.updates import router
from app.services.releases.config import PREFIX
from app.services.releases.manifest import ReleaseManifest
from app.services.releases.publisher import PublishRequest, ReleasePublisher, inspect_package
from app.services.releases.service import ReleaseService
from app.services.releases.storage import ReleaseStorage


def pe_fixture():
    data = bytearray(128)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 60, 64)
    data[64:68] = b"PE\0\0"
    struct.pack_into("<H", data, 68, 0x14c)
    return bytes(data)


def missing():
    return ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")


class FakeS3:
    def __init__(self):
        self.objects = {}
        self.metadata = {}
        self.calls = []
        self.conflict = False
        self.upload_error = False

    def get_object(self, *, Bucket, Key):
        if Key not in self.objects:
            raise missing()
        return {"Body": io.BytesIO(self.objects[Key]), "ETag": '"etag-current"'}

    def list_objects_v2(self, *, Bucket, Prefix, **kwargs):
        return {"Contents": [{"Key": key} for key in self.objects if key.startswith(Prefix)]}

    def upload_file(self, path, bucket, key, *, ExtraArgs, Callback, Config):
        self.calls.append("upload")
        if self.upload_error:
            raise ClientError({"Error": {"Code": "AccessDenied", "Message": "do-not-expose"}}, "PutObject")
        from pathlib import Path
        self.objects[key] = Path(path).read_bytes()
        self.metadata[key] = ExtraArgs["Metadata"]
        Callback(len(self.objects[key]))

    def head_object(self, *, Bucket, Key):
        self.calls.append("head")
        return {"ContentLength": len(self.objects[Key]), "Metadata": {"Sha256": self.metadata[Key]["sha256"]}}

    def put_object(self, *, Bucket, Key, Body, **kwargs):
        latest = Key.endswith("/latest.json")
        self.calls.append("commit" if latest else "record")
        if self.conflict and latest:
            raise ClientError({"Error": {"Code": "PreconditionFailed"}}, "PutObject")
        if latest and Key in self.objects:
            assert kwargs["IfMatch"] == '"etag-current"'
        elif latest:
            assert kwargs["IfNoneMatch"] == "*"
        self.objects[Key] = Body


@pytest.fixture
def publishing(tmp_path):
    source = tmp_path / "NovelisCargoHubSetup-0.1.35.exe"
    source.write_bytes(pe_fixture())
    client = FakeS3()
    config = SimpleNamespace(enabled=lambda: True, client=lambda: client)
    storage = ReleaseStorage(config)
    publisher = ReleasePublisher(tmp_path, storage)
    request = PublishRequest(installer_path=str(source), version="0.1.35", notes="Correções autorizadas", distribution_authorized=True)
    return publisher, request, client, source


def test_publishes_package_before_manifest_and_supports_safe_retry(publishing):
    publisher, body, client, source = publishing
    async def run():
        assert publisher.start(body)["status"] == "validating"
        original_task = publisher.task
        publisher.start(body)
        assert publisher.task is original_task
        await publisher.task
        assert publisher.snapshot()["status"] == "published"
        assert client.calls == ["upload", "head", "record", "commit"]
        manifest = ReleaseManifest.model_validate_json(client.objects[PREFIX + "latest.json"])
        assert client.objects[PREFIX + manifest.package_key()] == source.read_bytes()
        assert manifest.sha256 == hashlib.sha256(source.read_bytes()).hexdigest()
        publisher.start(body)
        await publisher.task
        assert publisher.snapshot()["status"] == "published"
        assert client.calls == ["upload", "head", "record", "commit"]
    asyncio.run(run())


def test_publishing_requires_developer_mode_and_distribution_authorization(publishing):
    publisher, body, _, _ = publishing
    with pytest.raises(ValueError, match="autorização"):
        publisher.start(body.model_copy(update={"distribution_authorized": False}))
    publisher.storage.config.enabled = lambda: False
    with pytest.raises(PermissionError):
        publisher.start(body)


@pytest.mark.parametrize("suffix", ["PRIVADO", "TESTE", "NaoDistribuir"])
def test_restricted_packages_cannot_be_published(tmp_path, suffix):
    path = tmp_path / f"NovelisCargoHubSetup-0.1.35-{suffix}.exe"
    path.write_bytes(pe_fixture())
    with pytest.raises(ValueError, match="privado ou teste"):
        inspect_package(path, "0.1.35")


def test_receipt_blocks_private_configuration_and_pending_approval(publishing):
    _, _, _, source = publishing
    for receipt in [{"production_ready": False}, {"operational_configuration": {"contains_operational_credentials": True}}, {"build_mode": "development"}]:
        source.with_suffix(".manifest.json").write_text(json.dumps(receipt))
        with pytest.raises(ValueError, match="distribuição pendente"):
            inspect_package(source, "0.1.35")


def test_upload_failure_does_not_publish_manifest_or_expose_sdk_error(publishing):
    publisher, body, client, _ = publishing
    client.upload_error = True
    async def run():
        publisher.start(body)
        await publisher.task
        result = publisher.snapshot()
        assert result["status"] == "error"
        assert "do-not-expose" not in json.dumps(result)
        assert PREFIX + "latest.json" not in client.objects
        assert not list(publisher.root.rglob("*.exe"))
    asyncio.run(run())


def test_concurrent_publication_cannot_overwrite_changed_manifest(publishing):
    publisher, body, client, _ = publishing
    client.conflict = True
    async def run():
        publisher.start(body)
        await publisher.task
        assert publisher.snapshot()["status"] == "error"
        assert "simultâneas" in publisher.snapshot()["message"]
        assert PREFIX + "latest.json" not in client.objects
    asyncio.run(run())


def test_older_release_is_rejected_before_upload(publishing):
    publisher, body, client, _ = publishing
    async def run():
        publisher.start(body)
        await publisher.task
        publisher.start(body.model_copy(update={"version": "0.1.34"}))
        await publisher.task
        assert publisher.snapshot()["status"] == "error"
        assert client.calls == ["upload", "head", "record", "commit"]
    asyncio.run(run())


def test_authenticated_check_and_download_use_private_storage(publishing, tmp_path):
    publisher, body, _client, _ = publishing
    def anonymous_is_forbidden(request):
        raise AssertionError("The authenticated flow must use S3")
    async def run():
        service = ReleaseService(tmp_path, "0.1.34", httpx.MockTransport(anonymous_is_forbidden))
        service.storage = publisher.storage
        assert (await service.check())["status"] == "not_published"
        publisher.start(body)
        await publisher.task
        assert (await service.check())["status"] == "available"
        service.start_download()
        await service.task
        assert service.snapshot()["status"] == "ready"
    asyncio.run(run())


def test_manifest_object_path_is_bound_to_hash_and_filename():
    with pytest.raises(ValueError):
        ReleaseManifest(version="0.1.35", published_at="2026-11-13T00:00:00Z", file="NovelisCargoHubSetup-0.1.35.exe",
                        sha256="a" * 64, size=1, object_key="../outside.exe")


def test_catalog_repairs_a_stale_latest_pointer(publishing, tmp_path):
    publisher, body, client, _ = publishing
    async def run():
        publisher.start(body)
        await publisher.task
        original = client.objects[PREFIX + "latest.json"]
        source = tmp_path / "NovelisCargoHubSetup-0.1.36.exe"
        source.write_bytes(pe_fixture() + b"new")
        publisher.start(body.model_copy(update={"version": "0.1.36", "installer_path": str(source)}))
        await publisher.task
        client.objects[PREFIX + "latest.json"] = original
        active = publisher.storage.commit_manifest(client, ReleaseManifest.model_validate_json(original))
        assert active.version == "0.1.36"
        assert json.loads(client.objects[PREFIX + "latest.json"])["version"] == "0.1.36"
    asyncio.run(run())


def test_publishing_http_routes_require_session_and_both_local_files(publishing, tmp_path):
    publisher, body, _, _ = publishing
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.state.settings = SimpleNamespace(backend_root=tmp_path)
    app.state.session_audit = SimpleNamespace(session=lambda token: {"id": token} if token == "unit-session" else None)
    app.state.release_publisher = publisher
    with TestClient(app) as client:
        url = "/api/hub/developer/releases/publish"
        assert client.get(url).status_code == 401
        headers = {"X-Operator-Session": "unit-session"}
        assert client.get(url, headers=headers).status_code == 403
        (tmp_path / "CONFIG.dev").write_text("DEVMODE=1")
        (tmp_path / "credentials.json").write_text("{}")
        assert client.get(url, headers=headers).status_code == 200
        assert client.post(url, json=body.model_copy(update={"distribution_authorized": False}).model_dump(), headers=headers).status_code == 409
        assert client.post(url, json=body.model_dump(), headers=headers).status_code == 202
        for _ in range(100):
            result = client.get(url, headers=headers).json()
            if result["status"] in {"published", "error"}:
                break
            time.sleep(0.01)
        assert result["status"] == "published"
