import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers.operator_features import router
from app.domain.run_state import RunState
from app.infrastructure.session_audit_db import connection
from app.services.developer_monitor import recent, snapshot
from app.services.device_presence import DevicePresence
from app.services.session_audit import SessionAudit


@pytest.fixture
def system(tmp_path):
    root = tmp_path / "installed"
    root.mkdir()
    (root / ".automacao-novelis-install").touch()
    (root / "installed-release.json").write_text(json.dumps({"version": "0.1.35-r2"}))
    identity = lambda: {"windows_user": "DOMAIN\\operator", "computer_name": "TEST-PC", "mac_addresses": ["00:11:22:33:44:55"]}
    audit = SessionAudit(tmp_path / "local/audit.sqlite", tmp_path / "shared/logs/sessoes.sqlite", identity)
    state = RunState(audit=audit)
    clock = [datetime.now(UTC)]
    presence = DevicePresence(audit, root, state, clock=lambda: clock[0])
    return SimpleNamespace(root=root, audit=audit, state=state, clock=clock, presence=presence)


def test_inventory_registers_an_installation_before_operator_login(system):
    asyncio.run(system.presence.tick())
    system.audit.sync()
    view = snapshot(system.audit, system.clock[0])
    assert view["summary"] == {"detected_installations": 1, "online_devices": 1,
        "logged_in_users": 0, "running_automations": 0, "broken_automations": 0}
    device = view["devices"][0]
    assert device["installation_kind"] == "installed" and device["version"] == "0.1.35-r2"
    assert device["mac_addresses"] == ["00:11:22:33:44:55"]
    assert device["operators"] == []
    assert "instance_id" not in device


def test_a_checkout_is_not_reported_as_an_installed_client(system):
    (system.root / ".automacao-novelis-install").unlink()
    asyncio.run(system.presence.tick())
    system.audit.sync()
    view = snapshot(system.audit, system.clock[0])
    assert view["summary"]["detected_installations"] == 0
    assert view["devices"][0]["installation_kind"] == "development"


def test_source_marker_without_installed_version_does_not_confirm_installation(system):
    (system.root / "installed-release.json").unlink()
    asyncio.run(system.presence.tick())
    system.audit.sync()
    assert snapshot(system.audit, system.clock[0])["devices"][0]["installation_kind"] == "development"


def test_background_heartbeat_refreshes_sessions_and_live_automation(system):
    actor = system.audit.login("Operador de teste", {"status": "idle"})
    async def run():
        await system.state.start("pendentes", False)
        system.clock[0] += timedelta(seconds=40)
        await system.presence.tick()
    asyncio.run(run())
    system.audit.sync()
    view = snapshot(system.audit, system.clock[0])
    assert view["summary"]["logged_in_users"] == 1
    assert view["summary"]["running_automations"] == 1
    assert view["devices"][0]["operators"] == ["Operador de teste"]
    assert view["sessions"][0]["display_status"] == "active"
    assert actor["id"] not in json.dumps(view)
    assert view["sessions"][0]["automation_status"] == "running"


def test_stale_clients_do_not_remain_logged_in_or_running(system):
    system.audit.login("Operador", {"status": "idle"})
    async def run():
        await system.state.start("pendentes", False)
        await system.presence.tick()
    asyncio.run(run())
    system.audit.sync()
    view = snapshot(system.audit, system.clock[0] + timedelta(seconds=91))
    assert view["summary"]["online_devices"] == view["summary"]["logged_in_users"] == view["summary"]["running_automations"] == 0
    assert view["summary"]["detected_installations"] == 1
    assert view["sessions"][0]["display_status"] == "stale"
    assert not view["devices"][0]["online"]
    assert view["devices"][0]["automation_status"] == "running"


def test_exit_ends_sessions_and_records_offline_without_claiming_uninstall(system):
    actor = system.audit.login("Operador", {"status": "idle"})
    asyncio.run(system.presence.tick())
    system.audit.sync()
    system.clock[0] += timedelta(seconds=1)
    asyncio.run(system.presence.close())
    system.audit.sync()
    view = snapshot(system.audit, system.clock[0])
    assert not view["devices"][0]["online"]
    assert view["summary"]["detected_installations"] == 1
    assert view["sessions"][0]["status"] == "interrupted"
    assert view["sessions"][0]["logout_at"]
    assert system.audit.session(actor["id"]) is None


def test_reinstall_updates_version_and_path_without_duplicating_the_device(system, tmp_path):
    asyncio.run(system.presence.tick())
    system.audit.sync()
    first = snapshot(system.audit, system.clock[0])["devices"][0]
    moved = tmp_path / "new-root"
    moved.mkdir()
    (moved / ".automacao-novelis-install").touch()
    (moved / "installed-release.json").write_text(json.dumps({"version": "0.1.36"}))
    system.clock[0] += timedelta(hours=1)
    replacement = DevicePresence(system.audit, moved, system.state, clock=lambda: system.clock[0])
    asyncio.run(replacement.tick())
    system.audit.sync()
    view = snapshot(system.audit, system.clock[0])
    assert len(view["devices"]) == 1
    assert view["devices"][0]["id"] == first["id"]
    assert view["devices"][0]["first_seen_at"] == first["first_seen_at"]
    assert view["devices"][0]["version"] == "0.1.36"
    assert view["devices"][0]["install_root"] == str(moved)
    system.clock[0] += timedelta(seconds=1)
    asyncio.run(system.presence.close())
    system.audit.sync()
    assert snapshot(system.audit, system.clock[0])["devices"][0]["online"]


def test_heartbeat_queue_is_bounded_and_survives_shared_storage_outage(system, tmp_path):
    system.audit.login("Operador", {"status": "idle"})
    for _ in range(4):
        system.clock[0] += timedelta(seconds=30)
        asyncio.run(system.presence.tick())
    assert system.audit.pending() == 2
    destination = system.audit.shared_path
    blocked = tmp_path / "blocked"
    blocked.write_text("fixture")
    system.audit.shared_path = blocked / "audit.sqlite"
    with pytest.raises(OSError):
        system.audit.sync()
    assert system.audit.pending() == 2
    system.audit.shared_path = destination
    assert system.audit.sync() == 2
    assert snapshot(system.audit, system.clock[0])["summary"]["online_devices"] == 1


def test_legacy_sessions_are_visible_with_installation_unconfirmed(system):
    system.audit.login("Operador legado", {"status": "idle"})
    system.audit.sync()
    view = snapshot(system.audit, system.clock[0])
    assert view["devices"][0]["installation_kind"] == "unreported"
    assert view["devices"][0]["version"] is None
    assert view["summary"]["detected_installations"] == 0
    assert view["summary"]["logged_in_users"] == 1


def test_devices_and_sessions_from_other_computers_are_read_from_shared_storage(system, tmp_path):
    other = SessionAudit(tmp_path / "other/audit.sqlite", system.audit.shared_path,
        identity=lambda: {"windows_user": "DOMAIN\\other", "computer_name": "OTHER-PC", "mac_addresses": []})
    other.login("Outro operador", {"status": "failed"})
    presence = DevicePresence(other, system.root, RunState(), clock=lambda: system.clock[0])
    asyncio.run(presence.tick())
    other.sync()
    view = snapshot(system.audit, system.clock[0])
    assert view["devices"][0]["computer_name"] == "OTHER-PC"
    assert view["sessions"][0]["operator_name"] == "Outro operador"


def test_older_inventory_updates_cannot_overwrite_a_newer_signal(system):
    asyncio.run(system.presence.tick())
    old = system.presence.device({"status": "idle"})
    system.clock[0] += timedelta(minutes=1)
    asyncio.run(system.presence.tick())
    system.audit.sync()
    from app.infrastructure.session_audit_db import apply
    with connection(system.audit.shared_path) as db:
        apply(db, {"device": old})
    assert snapshot(system.audit, system.clock[0])["devices"][0]["last_seen_at"] == system.clock[0].isoformat()


@pytest.mark.parametrize("seconds,expected", [(90, True), (91, False), (-16, False)])
def test_online_threshold_and_future_clock_skew(seconds, expected):
    now = datetime.now(UTC)
    assert recent((now - timedelta(seconds=seconds)).isoformat(), now) is expected


def test_developer_api_requires_an_operator_session_and_local_developer_files(system):
    backend_root = system.root / "BACKEND"
    backend_root.mkdir()
    actor = system.audit.login("Dev de teste", {"status": "idle"})
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.state.session_audit = system.audit
    app.state.settings = SimpleNamespace(backend_root=backend_root)
    headers = {"X-Operator-Session": actor["id"]}
    with TestClient(app) as client:
        assert client.get("/api/hub/developer/monitor").status_code == 401
        assert client.get("/api/hub/developer/monitor", headers=headers).status_code == 403
        (backend_root / "CONFIG.dev").write_text("DEVMODE=1")
        assert client.get("/api/hub/developer/monitor", headers=headers).status_code == 403
        (backend_root / "credentials.json").write_text("{}")
        response = client.get("/api/hub/developer/monitor", headers=headers)
        assert response.status_code == 200
        assert response.json()["source"] == "shared_session_audit"
        (backend_root / "CONFIG.dev").write_text("DEVMODE=0")
        assert client.get("/api/hub/developer/monitor", headers=headers).status_code == 403


def test_real_application_lifecycle_starts_presence_and_reports_shutdown(system, monkeypatch):
    from app import main
    from app.config.settings import Settings
    from app.services.notifications import NotificationService

    base = Settings(_env_file=None).model_dump()
    backend_root = system.root / "BACKEND"
    backend_root.mkdir()
    (backend_root / "CONFIG.dev").write_text("DEVMODE=1")
    (backend_root / "credentials.json").write_text("{}")
    base.update(backend_root=backend_root, storage_dir=system.root / "runtime",
                novelis_sqlite_path=system.root / "operations.sqlite",
                login_audit_db_path=system.audit.shared_path, cors_origins=[])
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace(**base))
    monkeypatch.setattr(NotificationService, "refresh", lambda self: None)
    app = main.create_app()
    app.state.session_audit.identity = system.audit.identity
    with TestClient(app) as client:
        result = client.post("/api/hub/session", json={"operator_name": "Operador de integração"})
        assert result.status_code == 200
        client.portal.call(app.state.device_presence.tick)
        app.state.session_audit.sync()
        result = client.get("/api/hub/developer/monitor", headers={"X-Operator-Session": result.json()["session"]["id"]})
        assert result.status_code == 200
        assert result.json()["summary"]["online_devices"] == 1
        assert result.json()["summary"]["logged_in_users"] == 1
    assert app.state.device_presence.task.done()
    view = snapshot(app.state.session_audit)
    assert view["devices"][0]["backend_status"] == "stopped"
    assert not view["devices"][0]["online"]
    assert view["sessions"][0]["status"] == "interrupted"


def test_shared_storage_failure_returns_clear_error_and_no_private_details(system, monkeypatch):
    from app.api.routers import operator_features
    actor = system.audit.login("Dev", {"status": "idle"})
    backend_root = system.root / "BACKEND"
    backend_root.mkdir()
    (backend_root / "CONFIG.dev").write_text("DEVMODE=1")
    (backend_root / "credentials.json").write_text("{}")
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.state.settings = SimpleNamespace(backend_root=backend_root)
    app.state.session_audit = system.audit
    def fail(audit):
        raise OSError("internal path must not be returned")
    monkeypatch.setattr(operator_features, "monitor_snapshot", fail)
    with TestClient(app) as client:
        result = client.get("/api/hub/developer/monitor", headers={"X-Operator-Session": actor["id"]})
        assert result.status_code == 503
        assert "registro compartilhado" in result.json()["detail"]
        assert "internal path" not in result.text


def test_installer_readiness_checks_api_without_starting_jobs_or_interrupting_sessions(system, monkeypatch):
    from unittest.mock import AsyncMock, Mock

    from app import main
    from app.config.settings import Settings

    values = Settings(_env_file=None).model_dump()
    values.update(backend_root=system.root / "BACKEND", storage_dir=system.root / "runtime",
                  novelis_sqlite_path=system.root / "operations.sqlite",
                  login_audit_db_path=system.audit.shared_path, cors_origins=[])
    values["backend_root"].mkdir()
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace(**values))
    monkeypatch.setenv("NOVELIS_BACKEND_READINESS", "1")
    app = main.create_app()
    app.state.session_audit.identity = system.audit.identity
    actor = app.state.session_audit.login("Sessão anterior", {"status": "idle"})
    app.state.scheduler.start = Mock(side_effect=AssertionError("readiness started automation"))
    app.state.session_audit.recover = Mock(side_effect=AssertionError("readiness interrupted sessions"))
    app.state.run_state.restore = AsyncMock(side_effect=AssertionError("readiness changed the previous run"))
    with TestClient(app) as client:
        assert client.get("/api/hub/health/ping").status_code == 200
        assert app.state.device_presence is None
        assert app.state.diagnostic_agent is None
        assert not hasattr(app.state, "notification_sync_task")
    assert app.state.session_audit.session(actor["id"])
    assert app.state.session_audit.pending() == 1
