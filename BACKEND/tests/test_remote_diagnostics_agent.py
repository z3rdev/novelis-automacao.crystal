import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.services.remote_diagnostics.agent import DiagnosticAgent


def agent(queue, instance="this-instance", runner=None):
    presence = SimpleNamespace(instance_id=instance, device=lambda snapshot: {"id": "this-device"})
    config = SimpleNamespace(values={"SQL_PASS": "fixture-secret"}, bool=lambda *args: True)
    return DiagnosticAgent(None, config, presence, queue, runner=runner or AsyncMock())


def test_agent_claims_only_its_device_and_redacts_the_result():
    queue = Mock()
    queue.claim.return_value = {"id": "request-1", "options": {"max_runs": 5, "days_back": 1}}
    runner = AsyncMock()
    runner.collect.return_value = {
        "complete": False,
        "message": "fixture-secret",
        "password": "other-secret",
    }
    worker = agent(queue, runner=runner)

    async def run():
        await worker.tick()
        await worker.job

    asyncio.run(run())
    queue.claim.assert_called_once_with("this-device", "this-instance")
    queue.finish.assert_called_once_with(
        "request-1",
        "this-instance",
        {"complete": False, "message": "[oculto]", "password": "[oculto]"},
    )


def test_agent_does_not_overlap_two_local_probes():
    queue = Mock()
    queue.claim.return_value = {"id": "request-1", "options": {}}

    async def collect(options):
        await asyncio.sleep(3600)

    worker = agent(queue, runner=SimpleNamespace(collect=collect))

    async def run():
        await worker.tick()
        await asyncio.sleep(0)
        await worker.tick()
        assert queue.claim.call_count == 1
        await worker.close()

    asyncio.run(run())
    assert worker.job.cancelled()
    queue.finish.assert_called_once_with("request-1", "this-instance", error="agent_stopped")


@pytest.mark.parametrize(
    "failure", [ValueError("fixture-secret"), RuntimeError("connection secret")]
)
def test_vendor_exceptions_become_fixed_codes(failure):
    queue = Mock()
    runner = AsyncMock()
    runner.collect.side_effect = failure
    asyncio.run(agent(queue, runner=runner).execute({"id": "req", "options": {}}))
    queue.finish.assert_called_once_with("req", "this-instance", error="probe_unavailable")
