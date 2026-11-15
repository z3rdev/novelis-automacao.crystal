"""Opt-in integration against isolated QA tables; never requests another PC."""

import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from uuid import uuid4

import pytest

from app.config.legacy_config import LegacyConfig
from app.config.settings import Settings
from app.infrastructure.chamados_postgres import ChamadosPostgres
from app.infrastructure.diagnostic_queue import DiagnosticQueue, DiagnosticTargetUnavailable

pytestmark = pytest.mark.skipif(
    os.getenv("NOVELIS_DIAGNOSTIC_PG_TEST") != "1", reason="Isolated PostgreSQL test is opt-in"
)


@pytest.fixture(scope="module")
def isolated():
    from psycopg import sql

    config = LegacyConfig(Settings())
    database = ChamadosPostgres(config)
    prefix = "qa_diagnostic_" + uuid4().hex
    assert prefix.startswith("qa_diagnostic_") and len(prefix) == 46

    class IsolatedDatabase:
        enabled = True

        @contextmanager
        def connection(self):
            with database.connection() as db:

                class Proxy:
                    def execute(self, statement, params=None):
                        isolated_sql = statement.replace(
                            "cargo_hub_diagnostic_", prefix + "_"
                        ).replace("ix_diagnostic_target", prefix + "_index")
                        return db.execute(isolated_sql, params)

                yield Proxy()

    queue = DiagnosticQueue(config)
    queue.db = IsolatedDatabase()
    queue.ensure()
    try:
        yield queue
    finally:
        with database.connection() as db:
            for suffix in ("requests", "agents"):
                db.execute(
                    sql.SQL("DROP TABLE IF EXISTS public.{}").format(
                        sql.Identifier(prefix + "_" + suffix)
                    )
                )


@pytest.fixture
def queue(isolated):
    with isolated.db.connection() as db:
        db.execute(
            "TRUNCATE public.cargo_hub_diagnostic_requests,public.cargo_hub_diagnostic_agents"
        )
    return isolated


def register(queue, instance="instance-1"):
    device = {
        "id": str(uuid4()),
        "machine_id": "qa-simulated",
        "computer_name": "QA-SIMULATED",
        "version": "test",
        "installation_kind": "development",
    }
    queue.heartbeat(device, instance)
    return device


def test_concurrent_requests_collapse_to_one_active_collection(queue):
    device = register(queue)
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(
            pool.map(
                lambda _: queue.create(
                    device["id"], "QA\\developer", {"max_runs": 5, "days_back": 1}
                ),
                range(4),
            )
        )
    assert len({row["id"] for row in rows}) == 1
    assert len(queue.list()) == 1


def test_only_correct_target_and_instance_can_claim_and_finish(queue):
    device = register(queue)
    request = queue.create(device["id"], "QA\\developer", {})
    assert queue.claim(str(uuid4()), "instance-1") is None
    assert queue.claim(device["id"], "wrong-instance") is None
    assert queue.claim(device["id"], "instance-1")["id"] == request["id"]
    assert not queue.finish(request["id"], "wrong-instance", {"complete": True})
    assert queue.finish(request["id"], "instance-1", {"complete": False, "summary": {"issues": 1}})
    assert queue.get(request["id"])["result"]["complete"] is False
    assert queue.list()[0]["summary"]["issues"] == 1
    assert queue.get(request["id"])["state"] == "completed"


def test_parallel_claims_never_run_the_same_job_twice(queue):
    device = register(queue)
    queue.create(device["id"], "QA\\developer", {})
    with ThreadPoolExecutor(max_workers=4) as pool:
        claims = list(pool.map(lambda _: queue.claim(device["id"], "instance-1"), range(4)))
    assert sum(row is not None for row in claims) == 1


def test_expiry_and_late_results_do_not_resurrect_jobs(queue):
    device = register(queue)
    first = queue.create(device["id"], "QA\\developer", {})
    with queue.db.connection() as db:
        db.execute(
            "UPDATE public.cargo_hub_diagnostic_requests SET expires_at=now()-interval '1 second'"
        )
    assert queue.get(first["id"])["state"] == "expired"
    second = queue.create(device["id"], "QA\\developer", {})
    queue.claim(device["id"], "instance-1")
    with queue.db.connection() as db:
        db.execute(
            "UPDATE public.cargo_hub_diagnostic_requests SET lease_until=now()-interval '1 second' WHERE id=%s",
            (second["id"],),
        )
    assert not queue.finish(second["id"], "instance-1", {"complete": True})
    assert queue.get(second["id"])["state"] == "timed_out"


def test_previous_instance_shutdown_cannot_mark_replacement_offline(queue):
    device = register(queue)
    queue.heartbeat(device, "replacement")
    queue.leave(device["id"], "instance-1")
    assert queue.agents()[0]["online"] is True
    queue.leave(device["id"], "replacement")
    with pytest.raises(DiagnosticTargetUnavailable):
        queue.create(device["id"], "QA\\developer", {})


def test_real_local_probe_round_trip_through_api_and_agent(queue, tmp_path):
    import asyncio
    import json
    import socket
    from types import SimpleNamespace

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.routers.developer_diagnostics import router
    from app.services.remote_diagnostics.agent import DiagnosticAgent

    (tmp_path / "CONFIG.dev").write_text("DEVMODE=1")
    (tmp_path / "credentials.json").write_text("{}")
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.state.settings = SimpleNamespace(backend_root=tmp_path)
    app.state.session_audit = SimpleNamespace(
        session=lambda token: (
            {"windows_user": "QA\\developer"} if token == "fixture-session" else None
        )
    )
    app.state.diagnostic_queue = queue
    settings = Settings()
    config = LegacyConfig(settings)
    device = register(queue)
    device["computer_name"] = socket.gethostname()
    presence = SimpleNamespace(instance_id="instance-1", device=lambda snapshot: device)
    worker = DiagnosticAgent(settings, config, presence, queue)
    headers = {"X-Operator-Session": "fixture-session"}
    path = "/api/hub/developer/diagnostics"
    with TestClient(app) as http:
        response = http.post(
            path,
            headers=headers,
            json={"device_id": device["id"], "options": {"max_runs": 5, "days_back": 1}},
        )
        assert response.status_code == 202
        request = response.json()

        async def collect():
            await worker.tick()
            await worker.job

        asyncio.run(collect())
        received = http.get(path + "/" + request["id"], headers=headers)
        assert received.status_code == 200
        result = received.json()
        assert result["state"] == "completed"
        assert result["result"]["complete"] is True
        assert result["result"]["device"]["computer_name"] == socket.gethostname()
        assert any(
            item["id"] == "fiscal_export" and item["status"] == "not_tested"
            for item in result["result"]["checks"]
        )
        output = settings.backend_root.parent / "runtime/remote-diagnostics/local-round-trip.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
