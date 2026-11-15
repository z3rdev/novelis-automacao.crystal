import asyncio
import json
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers.sessions import router
from app.domain.run_state import RunState
from app.services.session_audit import SessionAudit, operator_session


def identity():
    return {"windows_user": "DOMAIN\\tester", "computer_name": "TEST-PC", "mac_addresses": ["00:11:22:33:44:55"]}


def audit(tmp_path):
    return SessionAudit(tmp_path / "local/audit.sqlite", tmp_path / "shared/logs/sessoes.sqlite", identity)


def test_login_records_trusted_identity_and_replicates_once(tmp_path):
    service = audit(tmp_path)
    session = service.login("Operador de teste", {"status": "idle"})
    assert session["windows_user"] == identity()["windows_user"]
    assert session["operator_name"] == "tester"
    assert session["mac_addresses"] == identity()["mac_addresses"]
    assert session["login_at"] and session["automation_status"] == "stopped"
    assert service.sync() == 1
    assert service.sync() == 0
    with sqlite3.connect(service.shared_path) as db:
        assert db.execute("SELECT operator_name,computer_name FROM sessions").fetchone() == ("tester", "TEST-PC")
        assert json.loads(db.execute("SELECT mac_addresses FROM sessions").fetchone()[0]) == identity()["mac_addresses"]


def test_run_transitions_keep_original_operator_after_logout_and_restart(tmp_path):
    service = audit(tmp_path)
    session = service.login("Operador", {"status": "idle"})

    async def run():
        state = RunState(audit=service)
        token = operator_session.set(session["id"])
        try:
            snapshot = await state.start("pendentes", False)
        finally:
            operator_session.reset(token)
        await state.update(current_step=1)
        service.logout(session["id"])
        await state.update(status="failed")
        return snapshot.id

    run_id = asyncio.run(run())
    service.sync()
    with sqlite3.connect(service.shared_path) as db:
        assert db.execute("SELECT status,session_id FROM automation_events WHERE run_id=? ORDER BY recorded_at", (run_id,)).fetchall() == [
            ("running", session["id"]), ("broken", session["id"])]
        assert db.execute("SELECT status,automation_status FROM sessions").fetchone() == ("logged_out", "broken")


def test_shared_failure_preserves_durable_queue_for_retry(tmp_path):
    service = audit(tmp_path)
    service.login("Operador", {"status": "idle"})
    blocked = tmp_path / "file-instead-of-directory"
    blocked.write_text("fixture")
    service.shared_path = blocked / "audit.sqlite"
    try:
        service.sync()
    except OSError:
        pass
    assert service.pending() == 1
    resumed = audit(tmp_path)
    assert resumed.sync() == 1
    assert resumed.pending() == 0


def test_backend_restart_marks_previous_sessions_interrupted(tmp_path):
    service = audit(tmp_path)
    session = service.login("Operador", {"status": "idle"})
    resumed = audit(tmp_path)
    resumed.recover()
    assert resumed.session(session["id"]) is None
    resumed.sync()
    with sqlite3.connect(resumed.shared_path) as db:
        assert db.execute("SELECT status FROM sessions").fetchone()[0] == "interrupted"

@pytest.mark.parametrize(("source", "expected"), [
    ("idle", "stopped"), ("running", "running"), ("stopping", "stopping"),
    ("completed", "completed"), ("failed", "broken"), ("cancelled", "cancelled"),
])
def test_all_automation_states_are_recorded(tmp_path, source, expected):
    service = audit(tmp_path)
    session = service.login("Operador", {"status": "idle"})
    service.record_run({"id": "run-states", "status": source}, session["id"])
    service.sync()
    with sqlite3.connect(service.shared_path) as db:
        assert db.execute("SELECT status FROM automation_events").fetchone()[0] == expected


def test_session_http_entry_points_use_backend_windows_identity(tmp_path):
    service = audit(tmp_path)
    app = FastAPI()
    app.state.session_audit = service

    class Automation:
        async def current(self):
            return await RunState().get()
    app.state.automation = Automation()
    app.include_router(router, prefix="/api")
    with TestClient(app) as client:
        assert client.get("/api/hub/session").json()["session"] is None
        response = client.post("/api/hub/session", json={
            "operator_name": "Operador HTTP", "windows_user": "UNTRUSTED"})
        assert response.status_code == 200
        session = response.json()["session"]
        assert session["windows_user"] == "DOMAIN\\tester"
        headers = {"X-Operator-Session": session["id"]}
        assert client.get("/api/hub/session", headers=headers).json()["session"]["id"] == session["id"]
        assert client.delete("/api/hub/session", headers=headers).status_code == 204
        assert client.get("/api/hub/session", headers=headers).json()["session"] is None
        assert client.post("/api/hub/session", json={"operator_name": " "}).status_code == 422
