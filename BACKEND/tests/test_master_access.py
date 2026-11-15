from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers.master_access import router
from app.api.deps import require_master_access
from app.infrastructure.operations_store import OperationsStore
from app.services.master_access import MasterAccess, MasterDenied, GRANT_SECONDS

PASSWORD = "test-only-not-a-production-key"
ACTOR = {"id": "session-one", "windows_user": "TEST\\operator", "computer_name": "TEST-PC"}


@pytest.fixture
def service(tmp_path):
    store = OperationsStore(tmp_path / "shared.sqlite")
    store.initialize()
    value = MasterAccess(store)
    yield value
    store.close()


def test_policy_shared_between_machines_but_grants_are_session_local(service):
    other_store = OperationsStore(service.store.path, machine_id="another-pc")
    other_store.initialize()
    other = MasterAccess(other_store)
    actor = {**ACTOR, "id": "session-two", "computer_name": "ANOTHER-PC"}
    assert service.setup(PASSWORD, ACTOR, can_setup=True)["unlocked"]
    assert other.status(actor)["configured"]
    assert not other.status(actor)["unlocked"]
    assert other.unlock(PASSWORD, actor)["unlocked"]
    assert not other.status(ACTOR)["unlocked"]
    with service.store.connection() as db:
        row = db.execute("SELECT salt,digest,rounds FROM hub_master_policy").fetchone()
    assert PASSWORD not in str(row)
    assert row[2] == 600_000
    assert PASSWORD.encode() not in service.store.path.read_bytes()
    other_store.close()


def test_initial_setup_requires_developer_and_cannot_overwrite_existing_policy(service):
    with pytest.raises(MasterDenied):
        service.setup(PASSWORD, ACTOR)
    with pytest.raises(ValueError):
        service.setup("short", ACTOR, can_setup=True)
    service.setup(PASSWORD, ACTOR, can_setup=True)
    with pytest.raises(MasterDenied):
        service.setup("different-test-key", ACTOR, can_setup=True)
    service.lock(ACTOR)
    assert service.unlock(PASSWORD, ACTOR)["unlocked"]


def test_parallel_setup_has_one_winner(service):
    another = OperationsStore(service.store.path, machine_id="second")
    another.initialize()
    def setup(value):
        try:
            value.setup(PASSWORD, ACTOR, can_setup=True)
            return True
        except MasterDenied:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(setup, [service, MasterAccess(another)])) == [False, True]
    another.close()


def test_developer_manages_one_shared_policy_and_rotation_revokes_other_backends(service):
    another_store = OperationsStore(service.store.path, machine_id="second")
    another_store.initialize()
    another = MasterAccess(another_store)
    service.save_policy(PASSWORD, ACTOR, can_manage=True)
    assert not service.status(ACTOR)["unlocked"]
    actor = {**ACTOR, "id": "second-session"}
    assert another.unlock(PASSWORD, actor)["unlocked"]
    changed = service.save_policy("new-test-only-password", ACTOR, can_manage=True)
    assert changed["configured"] and changed["updated_by"] == ACTOR["windows_user"]
    assert "digest" not in changed and "salt" not in changed
    with pytest.raises(MasterDenied):
        another.require(actor)
    with pytest.raises(MasterDenied, match="incorreta"):
        another.unlock(PASSWORD, actor)
    assert another.unlock("new-test-only-password", actor)["unlocked"]
    with pytest.raises(MasterDenied):
        service.save_policy(PASSWORD, ACTOR)
    another_store.close()


def test_policy_management_api_is_developer_only_and_does_not_unlock_settings(service, tmp_path, monkeypatch):
    from app.api.routers import master_access
    app = FastAPI()
    app.state.settings = SimpleNamespace(backend_root=tmp_path)
    app.state.master_access = service
    app.state.session_audit = SimpleNamespace(session=lambda key: ACTOR if key == ACTOR["id"] else None)
    app.include_router(router, prefix="/api")
    headers = {"X-Operator-Session": ACTOR["id"]}
    with TestClient(app) as client:
        assert client.get("/api/hub/master-access/admin").status_code == 401
        monkeypatch.setattr(master_access, "can_setup", lambda request: False)
        assert client.get("/api/hub/master-access/admin", headers=headers).status_code == 403
        assert client.put("/api/hub/master-access/admin", headers=headers, json={"password": PASSWORD}).status_code == 403
        monkeypatch.setattr(master_access, "can_setup", lambda request: True)
        assert not client.get("/api/hub/master-access/admin", headers=headers).json()["configured"]
        saved = client.put("/api/hub/master-access/admin", headers=headers, json={"password": PASSWORD})
        assert saved.status_code == 200 and saved.json()["configured"]
        assert PASSWORD not in saved.text
        assert not client.get("/api/hub/master-access", headers=headers).json()["unlocked"]
        assert client.post("/api/hub/master-access/unlock", headers=headers, json={"password": PASSWORD}).status_code == 200
        assert client.put("/api/hub/master-access/admin", headers=headers, json={"password": "another-test-password"}).status_code == 200
        assert not client.get("/api/hub/master-access", headers=headers).json()["unlocked"]


def test_grant_expires_and_manual_lock_revokes(service):
    timestamp = [1000]
    service.clock = lambda: timestamp[0]
    service.setup(PASSWORD, ACTOR, can_setup=True)
    timestamp[0] += GRANT_SECONDS
    with pytest.raises(MasterDenied):
        service.require(ACTOR)
    service.unlock(PASSWORD, ACTOR)
    service.require(ACTOR)
    service.lock(ACTOR)
    with pytest.raises(MasterDenied):
        service.require(ACTOR)


def test_failed_attempts_survive_a_new_backend_and_delay_correct_password(service):
    timestamp = [1000]
    service.clock = lambda: timestamp[0]
    service.setup(PASSWORD, ACTOR, can_setup=True)
    service.lock(ACTOR)
    for _ in range(5):
        with pytest.raises(MasterDenied, match="incorreta"):
            service.unlock("wrong-test-password", ACTOR)
    restarted = MasterAccess(service.store, clock=lambda: timestamp[0])
    with pytest.raises(MasterDenied, match="Aguarde"):
        restarted.unlock(PASSWORD, ACTOR)
    timestamp[0] += 61
    assert restarted.unlock(PASSWORD, ACTOR)["unlocked"]


def test_http_requires_operator_and_verified_grant_and_handles_store_failure(service, tmp_path, monkeypatch):
    from fastapi import Depends
    from app.api.routers import master_access
    app = FastAPI()
    app.state.settings = SimpleNamespace(backend_root=tmp_path)
    app.state.master_access = service
    active = {"value": True}
    app.state.session_audit = SimpleNamespace(session=lambda key: ACTOR if key == ACTOR["id"] and active["value"] else None)
    app.include_router(router, prefix="/api")
    @app.get("/protected", dependencies=[Depends(require_master_access)])
    def protected():
        return {"ok": True}
    headers = {"X-Operator-Session": ACTOR["id"]}
    monkeypatch.setattr(master_access, "can_setup", lambda request: True)
    with TestClient(app) as client:
        assert client.get("/api/hub/master-access").status_code == 401
        assert client.get("/protected", headers=headers).status_code == 403
        response = client.post("/api/hub/master-access/setup", headers=headers, json={"password": PASSWORD})
        assert response.status_code == 200 and response.json()["unlocked"]
        assert PASSWORD not in response.text
        assert client.get("/protected", headers=headers).status_code == 200
        assert client.delete("/api/hub/master-access", headers=headers).status_code == 204
        assert client.get("/protected", headers=headers).status_code == 403
        assert client.post("/api/hub/master-access/unlock", headers=headers, json={"password": "wrong-test-password"}).status_code == 403
        assert client.post("/api/hub/master-access/unlock", headers=headers, json={"password": PASSWORD}).status_code == 200
        active["value"] = False
        assert client.get("/protected", headers=headers).status_code == 401
        active["value"] = True
        monkeypatch.setattr(service, "_policy", lambda: (_ for _ in ()).throw(OSError("private path")))
        response = client.get("/api/hub/master-access", headers=headers)
        assert response.status_code == 503 and "private path" not in response.text
        assert client.get("/protected", headers=headers).status_code == 503


@pytest.mark.parametrize("path", ["/api/config", "/api/config/env", "/api/hub/config", "/api/hub/health/diagnostics"])
def test_actual_configuration_routes_deny_direct_unauthenticated_access(service, path):
    from app.api.routers.config import router as config_router
    from app.api.routers.hub import router as hub_router
    app = FastAPI()
    app.state.master_access = service
    app.state.session_audit = SimpleNamespace(session=lambda key: ACTOR)
    app.include_router(config_router, prefix="/api")
    app.include_router(hub_router, prefix="/api")
    with TestClient(app) as client:
        assert client.get(path).status_code == 401
        assert client.get(path, headers={"X-Operator-Session": ACTOR["id"]}).status_code == 403
