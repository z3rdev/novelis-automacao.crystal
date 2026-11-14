import asyncio
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.routers.health import _read_app_version, _read_release_version
from app.api.routers.updates import router
from app.services.releases.config import MANIFEST_URL, DeveloperConfig
from app.services.releases.manifest import ReleaseManifest, version_parts
from app.services.releases.service import ReleaseService

PACKAGE = b"MZ-test-installer-fixture"


def manifest(**changes):
    return {"schema_version": 1, "version": "0.1.34-r9", "title": "Cargo Hub atualizado",
            "notes": "Correções de teste", "published_at": "2026-11-13T17:00:00Z",
            "file": "NovelisCargoHubSetup-0.1.34-r9.exe", "size": len(PACKAGE),
            "sha256": hashlib.sha256(PACKAGE).hexdigest(), "architecture": "x64", **changes}


def release_service(tmp_path, payload=None, package=PACKAGE):
    def respond(request):
        if str(request.url) == MANIFEST_URL:
            return httpx.Response(200, json=payload or manifest())
        return httpx.Response(200, content=package)
    return ReleaseService(tmp_path, "0.1.34-r8", httpx.MockTransport(respond))


@pytest.mark.parametrize("credentials,marker,enabled", [
    (False, False, False), (False, True, False), (True, False, False), (True, True, True),
])
def test_developer_requires_both_local_files(tmp_path, credentials, marker, enabled):
    if credentials:
        (tmp_path / "credentials.json").write_text('{"secretKey":"unit-secret"}')
    if marker:
        (tmp_path / "CONFIG.dev").write_text("DEVMODE=1")
    config = DeveloperConfig(tmp_path)
    assert config.enabled() is enabled
    assert "unit-secret" not in json.dumps(config.status())
    if enabled:
        (tmp_path / "CONFIG.dev").unlink()
        assert config.enabled() is False


def test_disabled_marker_cannot_be_enabled_by_environment(tmp_path, monkeypatch):
    (tmp_path / "credentials.json").write_text("{}")
    (tmp_path / "CONFIG.dev").write_text("DEVMODE=0")
    monkeypatch.setenv("DEVMODE", "1")
    config = DeveloperConfig(tmp_path)
    assert config.enabled() is False
    with pytest.raises(PermissionError):
        config.probe()


def test_version_revision_and_installed_stamp(tmp_path):
    assert version_parts("0.1.34-r10") > version_parts("0.1.34-r9")
    assert version_parts("0.1.35") > version_parts("0.1.34-r999")
    (tmp_path / "installed-release.json").write_text('{"version":"0.1.34-r8"}')
    config = tmp_path / "DESKTOP/automacao_novelis_desktop/config.py"
    config.parent.mkdir(parents=True)
    config.write_text('APP_VERSION = "0.1.34"')
    assert _read_release_version(tmp_path) == "0.1.34-r8"
    assert _read_app_version(tmp_path) == "0.1.34"


@pytest.mark.parametrize("changes", [{"file": "../outside.exe"}, {"url": "https://untrusted.test/install.exe"},
                                    {"sha256": "abc"}, {"version": "broken"}, {"size": 0}])
def test_manifest_rejects_paths_urls_and_incomplete_integrity(changes):
    with pytest.raises(ValidationError):
        ReleaseManifest.model_validate(manifest(**changes))


def test_check_download_and_cache_reuse(tmp_path):
    async def run():
        service = release_service(tmp_path)
        assert (await service.check())["status"] == "available"
        assert service.start_download()["status"] == "downloading"
        task = service.task
        service.start_download()
        assert service.task is task
        await task
        assert service.snapshot()["status"] == "ready"
        assert service.package_path(service.release).read_bytes() == PACKAGE
        assert (await service.check())["status"] == "ready"
        restarted = release_service(tmp_path)
        await restarted.check()
        restarted.start_download()
        await restarted.task
        assert restarted.snapshot()["status"] == "ready"
    asyncio.run(run())


def test_corrupt_download_is_removed_and_can_retry(tmp_path):
    async def run():
        service = release_service(tmp_path, package=b"MZ-wrong-payload")
        await service.check()
        service.start_download()
        await service.task
        assert service.snapshot()["status"] == "error"
        assert not list(service.cache.rglob("*.partial"))
        assert not list(service.cache.rglob("*.exe"))
        service.transport = release_service(tmp_path).transport
        await service.check()
        service.start_download()
        await service.task
        assert service.snapshot()["status"] == "ready"
    asyncio.run(run())


def test_check_in_flight_cannot_replace_a_downloaded_package(tmp_path):
    async def run():
        service = release_service(tmp_path)
        await service.check()
        waiting, finish = asyncio.Event(), asyncio.Event()
        async def fetch():
            waiting.set()
            await finish.wait()
            return ReleaseManifest.model_validate(manifest(version="0.1.35"))
        service._fetch_manifest = fetch
        check = asyncio.create_task(service.check())
        await waiting.wait()
        service.start_download()
        await service.task
        finish.set()
        await check
        assert service.release.version == "0.1.34-r9"
        assert service.snapshot()["status"] == "ready"
    asyncio.run(run())


def test_parallel_update_checks_share_one_request(tmp_path):
    async def run():
        calls = 0
        async def respond(request):
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.01)
            return httpx.Response(200, json=manifest())
        service = ReleaseService(tmp_path, "0.1.34", httpx.MockTransport(respond))
        results = await asyncio.gather(service.check(), service.check(), service.check())
        assert calls == 1
        assert all(result["status"] == "available" for result in results)
    asyncio.run(run())


@pytest.mark.parametrize("http_status,expected", [(403, "error"), (404, "not_published"), (503, "error")])
def test_unavailable_feed_has_explicit_state(tmp_path, http_status, expected):
    service = ReleaseService(tmp_path, "0.1.34", httpx.MockTransport(lambda _: httpx.Response(http_status)))
    result = asyncio.run(service.check())
    assert result["status"] == expected
    assert result["release"] is None
    assert result["checked_at"]


def test_old_release_does_not_offer_downgrade(tmp_path):
    service = release_service(tmp_path, manifest(version="0.1.34-r7"))
    assert asyncio.run(service.check())["status"] == "up_to_date"


def test_install_rechecks_hash_and_does_not_run_changed_package(tmp_path, monkeypatch):
    launch = Mock()
    monkeypatch.setattr("app.services.releases.service.launch_installer", launch)
    (tmp_path / ".automacao-novelis-install").touch()
    async def run():
        service = release_service(tmp_path)
        await service.check()
        service.start_download()
        await service.task
        service.package_path(service.release).write_bytes(b"changed")
        with pytest.raises(ValueError):
            await service.install()
        launch.assert_not_called()
    asyncio.run(run())


def test_install_requires_installed_copy_and_runs_once(tmp_path, monkeypatch):
    process = Mock()
    process.poll.return_value = None
    launch = Mock(return_value=process)
    monkeypatch.setattr("app.services.releases.service.launch_installer", launch)
    async def run():
        service = release_service(tmp_path)
        await service.check()
        service.start_download()
        await service.task
        with pytest.raises(ValueError, match="cópia instalada"):
            await service.install()
        (tmp_path / ".automacao-novelis-install").touch()
        assert (await service.install())["status"] == "installing"
        await service.install()
        launch.assert_called_once_with(service.package_path(service.release), tmp_path)
        process.poll.return_value = 2
        assert service.snapshot()["status"] == "ready"
    asyncio.run(run())


def test_routes_gate_developer_and_installer_operations(tmp_path, monkeypatch):
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.state.settings = SimpleNamespace(backend_root=tmp_path)
    app.state.releases = release_service(tmp_path)
    app.state.session_audit = SimpleNamespace(session=lambda identifier: {"id": identifier} if identifier == "valid-session" else None)
    async def current():
        return SimpleNamespace(status="running")
    app.state.automation = SimpleNamespace(current=current)
    probe = Mock(return_value={"authenticated": True})
    monkeypatch.setattr(DeveloperConfig, "probe", probe)
    with TestClient(app) as client:
        assert client.get("/api/hub/developer").json()["enabled"] is False
        assert client.post("/api/hub/updates/download").status_code == 401
        headers = {"X-Operator-Session": "valid-session"}
        assert client.post("/api/hub/developer/releases/test", headers=headers).status_code == 403
        probe.assert_not_called()
        (tmp_path / "credentials.json").write_text("{}")
        (tmp_path / "CONFIG.dev").write_text("DEVMODE=1")
        assert client.post("/api/hub/developer/releases/test", headers=headers).status_code == 200
        assert client.post("/api/hub/updates/install", headers=headers).status_code == 409
