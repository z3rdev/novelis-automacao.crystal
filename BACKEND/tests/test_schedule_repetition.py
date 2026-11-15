import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.domain.automation_errors import AutomationBusyError
from app.domain.hub_features import ScheduleInput
from app.domain.run_state import RunState
from app.infrastructure.event_bus import EventBus
from app.infrastructure.operations_store import OperationsStore
from app.infrastructure.schedules import ScheduleRepository
from app.services.hub_service import HubService
from app.services.scheduler import ScheduleEngine
from app.services.session_audit import SessionAudit


@pytest.fixture
def system(tmp_path):
    store = OperationsStore(tmp_path / "operations.sqlite", "test-01")
    store.initialize()
    identity = lambda: {
        "windows_user": "DOMAIN\\operator",
        "computer_name": "TEST-01",
        "mac_addresses": [],
    }
    audit = SessionAudit(tmp_path / "audit.sqlite", tmp_path / "shared.sqlite", identity=identity)
    state, requests = RunState(store, audit), []

    async def start(request):
        snapshot = await state.start(request.flow, request.dry_run)
        requests.append(request)
        return snapshot

    automation = SimpleNamespace(current=state.get, start=start)
    events = EventBus(store=store)
    hub = HubService(
        SimpleNamespace(backend_root=tmp_path / "BACKEND"), None, store, automation, events, audit
    )
    actor = audit.login("Operador", {"status": "idle", "id": None})
    clock = [datetime(2026, 11, 16, 7, 59, tzinfo=timezone(timedelta(hours=-3)))]
    repo = ScheduleRepository(store)
    engine = ScheduleEngine(repo, hub, audit, events, clock=lambda: clock[0])
    yield SimpleNamespace(
        store=store,
        audit=audit,
        hub=hub,
        state=state,
        actor=actor,
        requests=requests,
        events=events,
        clock=clock,
        repo=repo,
        engine=engine,
    )
    store.close()


def save(system, **changes):
    return system.engine.save(ScheduleInput(name="Rotina", **changes), system.actor)


def last(system):
    return system.engine.list(system.actor["windows_user"])["schedules"][0]


def test_three_daily_slots_use_the_requested_interval_without_repeating(system):
    save(system, runs_per_day=3, interval_minutes=120)

    async def run():
        for index, hour in enumerate((8, 10, 12)):
            system.clock[0] = system.clock[0].replace(hour=hour)
            await asyncio.gather(system.engine.tick(), system.engine.tick())
            assert len(system.requests) == index + 1
            assert last(system)["last_run"]["slot"] == index
            await system.state.update(status="completed")
            await system.engine.tick()
            await system.engine.tick()
            assert len(system.requests) == index + 1
            assert last(system)["next_run_at"].startswith(
                f"2026-11-16T{hour + 2:02}:00" if index < 2 else "2026-11-17T08:00"
            )

    asyncio.run(run())


def test_failure_retries_only_up_to_the_limit_then_moves_to_next_day(system):
    save(system, max_retries=2, retry_interval_minutes=5)

    async def run():
        system.clock[0] = system.clock[0].replace(hour=8, minute=0)
        await system.engine.tick()
        for attempt in range(3):
            assert len(system.requests) == attempt + 1
            assert last(system)["last_run"]["attempt"] == attempt
            await system.state.update(status="failed", message="Falha controlada")
            await system.engine.tick()
            assert len(system.requests) == attempt + 1
            if attempt < 2:
                assert last(system)["next_attempt"] == attempt + 2
                system.clock[0] += timedelta(minutes=4)
                await system.engine.tick()
                assert len(system.requests) == attempt + 1
                system.clock[0] += timedelta(minutes=1)
                await system.engine.tick()
        assert last(system)["last_run"]["state"] == "failed"
        assert last(system)["next_run_at"].startswith("2026-11-17T08:00")
        await system.engine.tick()
        assert len(system.requests) == 3

    asyncio.run(run())


def test_successful_retry_preserves_the_next_daily_slot(system):
    save(system, runs_per_day=2, interval_minutes=60, max_retries=3, retry_interval_minutes=2)

    async def run():
        system.clock[0] = system.clock[0].replace(hour=8, minute=0)
        await system.engine.tick()
        await system.state.update(status="failed")
        await system.engine.tick()
        system.clock[0] += timedelta(minutes=2)
        await system.engine.tick()
        await system.state.update(status="completed")
        await system.engine.tick()
        assert len(system.requests) == 2
        assert last(system)["next_run_at"].startswith("2026-11-16T09:00")
        system.clock[0] = system.clock[0].replace(hour=9, minute=0)
        await system.engine.tick()
        assert len(system.requests) == 3
        assert last(system)["last_run"]["attempt"] == 0
        assert last(system)["last_run"]["slot"] == 1

    asyncio.run(run())


@pytest.mark.parametrize("status", ["completed", "cancelled"])
def test_completion_or_operator_stop_never_queues_a_failure_retry(system, status):
    save(system, max_retries=3)

    async def run():
        system.clock[0] = system.clock[0].replace(hour=8)
        await system.engine.tick()
        await system.state.update(status=status)
        await system.engine.tick()
        system.clock[0] += timedelta(minutes=20)
        await system.engine.tick()
        assert len(system.requests) == 1

    asyncio.run(run())


def test_waiting_retry_survives_restart_and_midnight(system):
    save(system, time="23:58", max_retries=1, retry_interval_minutes=5)

    async def run():
        system.clock[0] = system.clock[0].replace(hour=23, minute=58)
        await system.engine.tick()
        await system.state.update(status="failed")
        await system.engine.tick()
        restarted = ScheduleEngine(
            ScheduleRepository(system.store),
            system.hub,
            system.audit,
            system.events,
            clock=lambda: system.clock[0],
        )
        await restarted.recover()
        system.clock[0] += timedelta(minutes=5)
        await restarted.tick()
        assert len(system.requests) == 2
        occurrence = last(system)["last_run"]
        assert occurrence["attempt"] == 1 and occurrence["local_date"] == "2026-11-16"

    asyncio.run(run())


def test_edit_or_disable_cancels_waiting_retries(system):
    row = save(system, max_retries=2)

    async def run():
        system.clock[0] = system.clock[0].replace(hour=8)
        await system.engine.tick()
        await system.state.update(status="failed")
        await system.engine.tick()
        system.engine.save(
            ScheduleInput(name="Rotina", max_retries=2, enabled=False), system.actor, row["id"]
        )
        system.clock[0] += timedelta(minutes=10)
        await system.engine.tick()
        assert len(system.requests) == 1
        assert last(system)["next_run_at"] is None

    asyncio.run(run())


def test_busy_retry_is_released_without_consuming_an_attempt(system, monkeypatch):
    save(system, max_retries=1, retry_interval_minutes=1)

    async def run():
        system.clock[0] = system.clock[0].replace(hour=8)
        await system.engine.tick()
        await system.state.update(status="failed")
        await system.engine.tick()
        system.clock[0] += timedelta(minutes=1)
        original = system.engine._start_flow

        async def busy(*args, **kwargs):
            raise AutomationBusyError("Ocupado")

        monkeypatch.setattr(system.engine, "_start_flow", busy)
        await system.engine.tick()
        assert len(system.requests) == 1
        assert last(system)["next_attempt"] == 2
        monkeypatch.setattr(system.engine, "_start_flow", original)
        await system.engine.tick()
        assert len(system.requests) == 2

    asyncio.run(run())


def test_migration_preserves_legacy_daily_result_and_defaults(system):
    value = save(system)
    payload = {
        key: item
        for key, item in value.items()
        if key not in {"runs_per_day", "interval_minutes", "max_retries", "retry_interval_minutes"}
    }
    with system.store.connection() as db:
        db.execute(
            "UPDATE hub_schedules SET payload=? WHERE id=?", (json.dumps(payload), value["id"])
        )
        db.execute(
            "INSERT INTO hub_schedule_occurrences VALUES (?,?,?,NULL,NULL,?,?,?,?)",
            (
                value["id"],
                "2026-11-16",
                "completed",
                system.clock[0].isoformat(),
                system.clock[0].isoformat(),
                "Histórico legado",
                json.dumps(payload),
            ),
        )
    system.store.initialize()
    system.store.initialize()
    assert last(system)["runs_per_day"] == 1 and last(system)["max_retries"] == 0
    assert last(system)["next_run_at"].startswith("2026-11-17T08:00")


def test_slot_claims_are_atomic_and_block_overlapping_slots(system):
    row = save(system, runs_per_day=2)
    with ThreadPoolExecutor(max_workers=2) as executor:
        claimed = list(
            executor.map(
                lambda slot: system.repo.claim(row, "2026-11-16", system.clock[0], slot=slot),
                [0, 1],
            )
        )
    assert sorted(claimed) == [False, True]


@pytest.mark.parametrize(
    "changes",
    [
        {"runs_per_day": 0},
        {"runs_per_day": 49},
        {"interval_minutes": 0},
        {"max_retries": -1},
        {"max_retries": 11},
        {"retry_interval_minutes": 0},
        {"time": "23:00", "runs_per_day": 2, "interval_minutes": 60},
    ],
)
def test_invalid_frequency_and_retry_policy_is_rejected(changes):
    with pytest.raises(ValidationError):
        ScheduleInput(name="Rotina", **changes)


def test_history_keeps_each_attempt_and_requires_the_owner(system):
    value = save(system, max_retries=1)
    assert system.repo.claim(value, "2026-11-16", system.clock[0])
    system.repo.update(
        value["id"], "2026-11-16", "failed", "Falha controlada", finished=True, now=system.clock[0]
    )
    history = system.repo.history(value["id"], system.actor["windows_user"], size=1)
    assert history["total"] == 2 and history["rows"][0]["state"] == "waiting"
    assert (
        system.repo.history(value["id"], system.actor["windows_user"], page=1, size=1)["rows"][0][
            "state"
        ]
        == "failed"
    )
    with pytest.raises(KeyError):
        system.repo.history(value["id"], "DOMAIN\\another")


def test_history_api_requires_login_and_paginates(system):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.routers.operator_features import router

    value = save(system)
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.state.session_audit, app.state.scheduler = system.audit, system.engine
    endpoint = f"/api/hub/schedules/{value['id']}/history"
    headers = {"X-Operator-Session": system.actor["id"]}
    with TestClient(app) as client:
        assert client.get(endpoint).status_code == 401
        response = client.get(endpoint, headers=headers)
        assert response.status_code == 200 and response.json()["total"] == 0
        assert client.get(endpoint + "?size=0", headers=headers).status_code == 422
        assert client.get("/api/hub/schedules/missing/history", headers=headers).status_code == 404
