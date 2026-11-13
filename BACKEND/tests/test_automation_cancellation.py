import asyncio
import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.automation.cancellable_process import run_process
from app.automation.cancellation import (
    RunCancellation,
    cancellable_cursor,
    cancellation_scope,
    check_cancelled,
    run_blocking,
)
from app.domain.models import RunStartRequest
from app.domain.run_state import RunState
from app.infrastructure.event_bus import EventBus
from app.services.automation_service import AutomationService


def service(monkeypatch, coordinator):
    monkeypatch.setattr("app.services.automation_service.LegacyCoordinator", lambda *args: coordinator)
    value = AutomationService(SimpleNamespace(consulta_browser_headless=False), None, None,
                              EventBus(), RunState(), SimpleNamespace(close=AsyncMock()))
    value.STOP_WAIT_SECONDS = 0.02
    return value


def test_stop_before_first_task_tick_finishes_and_allows_a_new_run(monkeypatch):
    async def exercise():
        coordinator = SimpleNamespace(run=AsyncMock(return_value={}))
        value = service(monkeypatch, coordinator)
        await value.start(RunStartRequest(flow="consulta"))
        assert (await value.stop()).status == "cancelled"
        coordinator.run.assert_not_awaited()
        await value.start(RunStartRequest(flow="consulta"))
        await value._task
        assert (await value.current()).status == "completed"

    asyncio.run(exercise())


def test_slow_stop_logging_does_not_delay_cancelling_the_browser_task(monkeypatch):
    async def exercise():
        entered, aborted, release_log = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def flow(*args):
            entered.set()
            try:
                await asyncio.sleep(10)
            finally:
                aborted.set()

        value = service(monkeypatch, SimpleNamespace(run=flow))
        publish = value.event_bus.publish

        async def slow_publish(message, **kwargs):
            if kwargs.get("kind") == "run.stop_requested":
                await release_log.wait()
            return await publish(message, **kwargs)

        value.event_bus.publish = slow_publish
        await value.start(RunStartRequest(flow="consulta"))
        await entered.wait()
        stopping = asyncio.create_task(value.stop())
        try:
            await asyncio.wait_for(aborted.wait(), timeout=0.2)
        finally:
            release_log.set()
            await stopping
        assert (await value.current()).status == "cancelled"

    asyncio.run(exercise())


def test_cancel_waits_for_existing_io_and_blocks_restart_without_running_next_stage(monkeypatch):
    async def exercise():
        entered, release = threading.Event(), threading.Event()
        effects = []

        def slow_io():
            entered.set()
            release.wait(timeout=3)
            effects.append("io-finished")

        async def flow(*args):
            await run_blocking(slow_io)
            effects.append("next-stage")

        value = service(monkeypatch, SimpleNamespace(run=flow))
        await value.start(RunStartRequest(flow="consulta"))
        task = value._task
        while not entered.is_set():
            await asyncio.sleep(0.001)
        try:
            assert (await value.stop()).status == "stopping"
            assert (await value.stop()).status == "stopping"
            with pytest.raises(RuntimeError, match="encerrando"):
                await value.start(RunStartRequest(flow="consulta"))
        finally:
            release.set()
            await asyncio.wait_for(task, timeout=2)
        assert (await value.current()).status == "cancelled"
        assert effects == ["io-finished"]
        kinds = [event.kind for event in await value.event_bus.history()]
        assert kinds.count("run.cancelled") == 1
        assert kinds.count("run.stop_requested") == 1
        assert "run.completed" not in kinds

    asyncio.run(exercise())


def test_cooperative_scan_does_not_continue_to_next_item_after_cancel(monkeypatch):
    async def exercise():
        entered = threading.Event()
        visited = []

        def scan():
            for index in range(100):
                check_cancelled()
                visited.append(index)
                entered.set()
                time.sleep(0.005)

        async def flow(*args):
            await run_blocking(scan)

        value = service(monkeypatch, SimpleNamespace(run=flow))
        await value.start(RunStartRequest(flow="consulta"))
        task = value._task
        while not entered.is_set():
            await asyncio.sleep(0.001)
        await value.stop()
        await task
        count = len(visited)
        await asyncio.sleep(0.02)
        assert len(visited) == count < 100
        assert (await value.current()).status == "cancelled"

    asyncio.run(exercise())


def test_sql_resource_receives_cancel_and_worker_closes_before_terminal_state(monkeypatch):
    async def exercise():
        executing, cancelled = threading.Event(), threading.Event()
        closed = []

        class Cursor:
            def cancel(self):
                cancelled.set()

        def query():
            try:
                with cancellable_cursor(Cursor()):
                    executing.set()
                    cancelled.wait(timeout=3)
            finally:
                closed.append(True)

        async def flow(*args):
            await run_blocking(query)

        value = service(monkeypatch, SimpleNamespace(run=flow))
        await value.start(RunStartRequest(flow="consulta"))
        task = value._task
        while not executing.is_set():
            await asyncio.sleep(0.001)
        await value.stop()
        await task
        assert cancelled.is_set() and closed == [True]
        assert (await value.current()).status == "cancelled"

    asyncio.run(exercise())


def test_cancel_terminates_only_the_process_owned_by_the_worker(tmp_path):
    async def exercise():
        token = RunCancellation()
        marker = tmp_path / "entered.txt"
        code = "import pathlib,time;pathlib.Path('entered.txt').write_text('ready');time.sleep(10)"
        with cancellation_scope(token):
            task = asyncio.create_task(run_blocking(run_process, [sys.executable, "-c", code],
                                                    cwd=tmp_path, text=True, timeout=15, check=False))
            for _ in range(200):
                if marker.exists():
                    break
                await asyncio.sleep(0.01)
            assert marker.exists()
            token.request_cancel()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            await asyncio.wait_for(token.drain(), timeout=3)
        assert token.workers == set()

    asyncio.run(exercise())
