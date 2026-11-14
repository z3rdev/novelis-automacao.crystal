import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.routers.operator_features import router
from app.domain.automation_errors import AutomationBusyError
from app.domain.hub_features import NotificationInput, ScheduleInput
from app.domain.run_state import RunState
from app.infrastructure.event_bus import EventBus
from app.infrastructure.notifications import NotificationRepository
from app.infrastructure.operations_store import OperationsStore
from app.infrastructure.schedules import ScheduleRepository
from app.services.hub_service import HubService
from app.services.scheduler import ScheduleEngine
from app.services.session_audit import SessionAudit


class FakeAutomation:
    def __init__(self, store, audit):
        self.state = RunState(store, audit)
        self.requests = []
        self.busy = False

    async def current(self):
        return await self.state.get()

    async def start(self, request):
        if self.busy:
            raise AutomationBusyError("Ocupado")
        result = await self.state.start(request.flow, request.dry_run)
        self.requests.append(request)
        return result


@pytest.fixture
def system(tmp_path):
    store = OperationsStore(tmp_path / "operations.sqlite", "test-01")
    store.initialize()
    identity = lambda: {"windows_user": "DOMAIN\\operator", "computer_name": "TEST-01", "mac_addresses": []}
    audit = SessionAudit(tmp_path / "audit.sqlite", tmp_path / "shared-audit.sqlite", identity=identity)
    automation = FakeAutomation(store, audit)
    events = EventBus(store=store)
    hub = HubService(SimpleNamespace(backend_root=tmp_path / "BACKEND"), None, store, automation, events, audit)
    actor = audit.login("Operador de teste", {"status": "idle", "id": None})
    clock = [datetime(2026, 11, 16, 7, 59, tzinfo=timezone(timedelta(hours=-3)))]
    repository = ScheduleRepository(store)
    engine = ScheduleEngine(repository, hub, audit, events, clock=lambda: clock[0])
    yield SimpleNamespace(store=store, audit=audit, actor=actor, automation=automation, events=events,
        hub=hub, clock=clock, repository=repository, engine=engine, notices=NotificationRepository(store))
    store.close()


def test_notifications_are_shared_and_read_acknowledgements_are_per_windows_account(system):
    value = system.notices.publish(NotificationInput(title="Aviso importante", body="Texto <script>literal</script>"), system.actor)
    assert system.notices.list(system.actor["windows_user"])[0]["read_at"]
    other_store = OperationsStore(system.store.path, "test-02")
    other_store.initialize()
    other = NotificationRepository(other_store)
    assert other.list("DOMAIN\\other")[0]["read_at"] is None
    assert other.read(value["id"], "DOMAIN\\other")
    first = other.list("DOMAIN\\other")[0]["read_at"]
    assert other.read(value["id"], "domain\\OTHER")
    assert other.list("DOMAIN\\other")[0]["read_at"] == first
    assert other.list("DOMAIN\\third")[0]["read_at"] is None
    assert other.list("DOMAIN\\third")[0]["body"] == "Texto <script>literal</script>"
    assert system.notices.archive(value["id"])
    assert other.list("DOMAIN\\other") == []
    assert system.notices.list(system.actor["windows_user"], developer=True)[0]["archived_at"]


def test_notification_expiration_and_text_validation(system):
    with pytest.raises(ValidationError):
        NotificationInput(title="   ", body="Mensagem")
    with pytest.raises(ValueError):
        system.notices.publish(NotificationInput(title="Expirado", body="Mensagem", expires_at="2020-01-01T00:00:00Z"), system.actor)
    value = system.notices.publish(NotificationInput(title="Aviso futuro", body="Mensagem"), system.actor)
    with system.store.connection() as db:
        db.execute("UPDATE hub_notifications SET expires_at='2020-01-01T00:00:00+00:00' WHERE id=?", (value["id"],))
    assert system.notices.list("DOMAIN\\other") == []


@pytest.mark.parametrize("flow,days_back,sql_days,scope", [
    ("consulta", 0, 0, "full"), ("somente_pdf", 2, 3, "pdf"), ("completo", 5, 6, "full"),
])
def test_schedule_runs_at_eight_once_with_the_requested_flow_and_period(system, flow, days_back, sql_days, scope):
    value = system.engine.save(ScheduleInput(name="Rotina das oito", flow=flow, days_back=days_back), system.actor)
    async def run():
        await system.engine.tick()
        assert not system.automation.requests
        system.clock[0] = system.clock[0].replace(hour=8, minute=0)
        await asyncio.gather(system.engine.tick(), system.engine.tick())
        assert len(system.automation.requests) == 1
        request = system.automation.requests[0]
        assert request.pendentes_sql_days_back == sql_days
        assert request.execution_scope == scope
        assert request.flow == ("consulta-pendentes" if flow == "consulta" else "pendentes")
        assert not request.dry_run
        last = system.repository.list(system.actor["windows_user"])[0]["last_run"]
        assert last["state"] == "running"
        assert system.repository.active(system.actor["windows_user"])[0]["session_id"] != system.actor["id"]
        await system.automation.state.update(status="completed", message="Concluído")
        await system.engine.tick()
        assert len(system.automation.requests) == 1
        assert system.repository.list(system.actor["windows_user"])[0]["last_run"]["state"] == "completed"
        assert system.audit.session(system.actor["id"])
        assert any(event["kind"] == "schedule.started" for event in system.store.events())
    asyncio.run(run())
    assert value["next_run_at"].startswith("2026-11-16T08:00")


def test_busy_backend_waits_and_starts_after_the_current_run_finishes(system):
    system.engine.save(ScheduleInput(name="Após execução"), system.actor)
    async def run():
        await system.automation.state.start("consulta-pendentes", False)
        system.clock[0] = system.clock[0].replace(hour=8, minute=5)
        await system.engine.tick()
        assert not system.automation.requests
        assert system.repository.list(system.actor["windows_user"])[0]["last_run"] is None
        await system.automation.state.update(status="completed")
        await system.engine.tick()
        assert len(system.automation.requests) == 1
    asyncio.run(run())


def test_start_race_releases_the_daily_claim_for_retry(system):
    system.engine.save(ScheduleInput(name="Corrida de início"), system.actor)
    async def run():
        system.clock[0] = system.clock[0].replace(hour=8, minute=0)
        system.automation.busy = True
        await system.engine.tick()
        assert system.repository.list(system.actor["windows_user"])[0]["last_run"] is None
        system.automation.busy = False
        await system.engine.tick()
        assert len(system.automation.requests) == 1
    asyncio.run(run())


def test_saved_after_the_time_waits_for_the_next_selected_day(system):
    system.clock[0] = system.clock[0].replace(hour=9)
    row = system.engine.save(ScheduleInput(name="Amanhã"), system.actor)
    assert row["next_run_at"].startswith("2026-11-17T08:00")
    asyncio.run(system.engine.tick())
    assert not system.automation.requests


def test_disabled_and_wrong_weekday_schedules_do_not_run(system):
    system.engine.save(ScheduleInput(name="Desativada", enabled=False), system.actor)
    system.engine.save(ScheduleInput(name="Somente terça", weekdays=[1]), system.actor)
    system.clock[0] = system.clock[0].replace(hour=8, minute=30)
    asyncio.run(system.engine.tick())
    assert not system.automation.requests


def test_restart_marks_interrupted_occurrence_and_does_not_repeat_it(system):
    system.engine.save(ScheduleInput(name="Persistente"), system.actor)
    async def run():
        system.clock[0] = system.clock[0].replace(hour=8, minute=0)
        await system.engine.tick()
        restarted = ScheduleEngine(ScheduleRepository(system.store), system.hub, system.audit, system.events, clock=lambda: system.clock[0])
        await restarted.recover()
        await system.automation.state.restore()
        await restarted.tick()
        assert len(system.automation.requests) == 1
        assert restarted.list(system.actor["windows_user"])["schedules"][0]["last_run"]["state"] == "interrupted"
    asyncio.run(run())


def test_completed_run_is_reconciled_even_after_a_manual_run_replaces_it(system):
    system.engine.save(ScheduleInput(name="Histórico preservado"), system.actor)
    async def run():
        system.clock[0] = system.clock[0].replace(hour=8, minute=0)
        await system.engine.tick()
        await system.automation.state.update(status="completed", message="Concluído")
        await system.automation.state.start("pendentes", False)
        await system.engine.tick()
        assert system.repository.list(system.actor["windows_user"])[0]["last_run"]["state"] == "completed"
        assert len(system.automation.requests) == 1
    asyncio.run(run())


def test_claim_is_atomic_across_backend_instances_and_ownership_is_scoped(system):
    row = system.engine.save(ScheduleInput(name="Uma vez"), system.actor)
    other_store = OperationsStore(system.store.path, "test-02")
    other_store.initialize()
    assert ScheduleRepository(other_store).list(system.actor["windows_user"]) == []
    assert system.repository.list("DOMAIN\\other") == []
    same_machine_store = OperationsStore(system.store.path, "test-01")
    same_machine_store.initialize()
    repositories = [system.repository, ScheduleRepository(same_machine_store)]
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda index: repositories[index].claim(row, "2026-11-16", system.clock[0]), range(2)))
    assert sorted(results) == [False, True]


def test_dispatch_write_failure_is_reconciled_without_starting_again(system, monkeypatch):
    system.engine.save(ScheduleInput(name="Reconciliação"), system.actor)
    update = system.repository.update
    failed = [False]
    def unreliable(identifier, day, state, *args, **kwargs):
        if state == "running" and not failed[0]:
            failed[0] = True
            raise OSError("share unavailable")
        return update(identifier, day, state, *args, **kwargs)
    monkeypatch.setattr(system.repository, "update", unreliable)
    async def run():
        system.clock[0] = system.clock[0].replace(hour=8, minute=0)
        with pytest.raises(OSError):
            await system.engine.tick()
        assert len(system.automation.requests) == 1
        await system.engine.tick()
        assert len(system.automation.requests) == 1
        assert system.repository.list(system.actor["windows_user"])[0]["last_run"]["state"] == "running"
    asyncio.run(run())


def test_persistence_failure_before_dispatch_does_not_leave_the_execution_slot_busy():
    store = SimpleNamespace(save_run=Mock(side_effect=OSError("share unavailable")))
    state = RunState(store)
    async def run():
        with pytest.raises(OSError):
            await state.start("consulta-pendentes", False)
        assert (await state.get()).status == "idle"
        store.save_run.side_effect = None
        assert (await state.start("consulta-pendentes", False)).status == "running"
    asyncio.run(run())


@pytest.mark.parametrize("changes", [{"time": "24:00"}, {"days_back": 90}, {"weekdays": []}, {"weekdays": [7]}, {"flow": "unsupported"}])
def test_invalid_schedule_is_rejected(changes):
    with pytest.raises(ValidationError):
        ScheduleInput(name="Rotina válida", **changes)


def test_http_notifications_and_schedule_configuration(system, tmp_path):
    root = tmp_path / "BACKEND"
    root.mkdir()
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.state.settings = SimpleNamespace(backend_root=root)
    app.state.session_audit = system.audit
    app.state.notifications = system.notices
    app.state.scheduler = system.engine
    headers = {"X-Operator-Session": system.actor["id"]}
    with TestClient(app) as client:
        assert client.get("/api/hub/schedules").status_code == 401
        assert client.post("/api/hub/developer/notifications", json={"title": "Aviso", "body": "Mensagem"}, headers=headers).status_code == 403
        (root / "credentials.json").write_text("{}")
        (root / "CONFIG.dev").write_text("DEVMODE=1")
        response = client.post("/api/hub/developer/notifications", json={"title": "Aviso", "body": "Mensagem"}, headers=headers)
        assert response.status_code == 201
        notice = response.json()
        assert client.get("/api/hub/notifications", headers=headers).json()[0]["id"] == notice["id"]
        assert client.post(f"/api/hub/notifications/{notice['id']}/read", headers=headers).status_code == 200
        assert client.post(f"/api/hub/developer/notifications/{notice['id']}/archive", headers=headers).status_code == 200
        assert client.get("/api/hub/notifications", headers=headers).json() == []
        body = ScheduleInput(name="Rotina das oito", days_back=2).model_dump()
        result = client.post("/api/hub/schedules", json=body, headers=headers)
        assert result.status_code == 201
        identifier = result.json()["id"]
        assert client.get("/api/hub/schedules", headers=headers).json()["schedules"][0]["days_back"] == 2
        assert client.put(f"/api/hub/schedules/{identifier}", json={**body, "enabled": False}, headers=headers).json()["enabled"] is False
        assert client.delete(f"/api/hub/schedules/{identifier}", headers=headers).status_code == 204
        assert client.get("/api/hub/schedules", headers=headers).json()["schedules"] == []
