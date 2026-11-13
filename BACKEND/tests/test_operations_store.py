import asyncio
import sqlite3
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import pytest

from app.domain.run_state import RunState
from app.infrastructure.event_bus import EventBus
from app.infrastructure.operations_store import OperationsStore
from app.infrastructure.sqlite_lease import WriterLease


@pytest.fixture
def store(tmp_path):
    value = OperationsStore(tmp_path / "novelischamado.sqlite")
    value.initialize()
    yield value
    value.close()


def test_database_allows_multiple_local_backends(store):
    assert store.health()["journal_mode"] == "delete"
    other = OperationsStore(store.path, machine_id="other-pc")
    other.initialize()
    assert other.ready and store.ready
    other.close()


def test_file_lock_is_released_after_each_operation(store):
    lease = WriterLease(store.path)
    lease.acquire(timeout=0.1)
    other = WriterLease(store.path)
    try:
        with pytest.raises(RuntimeError, match="ocupado"):
            other.acquire(timeout=0.1)
    finally:
        lease.close()
    other.acquire(timeout=0.1)
    other.close()
    assert store.health()["ready"] is True


def _write_from_process(path, machine):
    store = OperationsStore(path, machine_id=machine)
    store.initialize()
    try:
        return [store.add_event({"run_id": machine, "message": str(index)}) for index in range(10)]
    finally:
        store.close()


def test_different_processes_share_one_database_without_losing_events(store):
    with ProcessPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(_write_from_process, store.path, f"pc-{index}") for index in range(3)]
        identifiers = [value for future in futures for value in future.result(timeout=30)]
    assert len(set(identifiers)) == 30
    assert len(store.events(all_machines=True)) == 30
    assert store.events() == []


def test_restarting_one_pc_does_not_fail_another_pcs_active_run(store):
    async def exercise():
        await RunState(store).start("pendentes", False)
        other = OperationsStore(store.path, machine_id="other-pc")
        other.initialize()
        try:
            restored = RunState(other)
            await restored.restore()
            assert (await restored.get()).status == "idle"
            assert store.last_run()["status"] == "running"
            store.preferences({"XML_SEFAZ_DOWNLOAD_DIR": "C:/pc-one"})
            other.preferences({"XML_SEFAZ_DOWNLOAD_DIR": "D:/pc-two"})
            assert store.preferences()["XML_SEFAZ_DOWNLOAD_DIR"] == "C:/pc-one"
            assert other.preferences()["XML_SEFAZ_DOWNLOAD_DIR"] == "D:/pc-two"
        finally:
            other.close()

    asyncio.run(exercise())


def test_missing_network_directory_does_not_create_a_fallback(tmp_path):
    store = OperationsStore(tmp_path / "missing-share" / "novelischamado.sqlite")
    with pytest.raises(RuntimeError, match="Pasta"):
        store.initialize()
    assert not store.path.exists()


def test_newer_database_is_not_silently_downgraded(tmp_path):
    path = tmp_path / "future.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA user_version=2")
    store = OperationsStore(path)
    with pytest.raises(RuntimeError, match="mais recente"):
        store.initialize()
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 2


def test_concurrent_requests_are_serialized_without_losing_events(store):
    def write(index):
        return store.add_event({"run_id": "one", "message": f"Evento {index}"})

    with ThreadPoolExecutor(max_workers=8) as pool:
        identifiers = list(pool.map(write, range(40)))
    assert len(set(identifiers)) == 40
    assert len(store.events("one")) == 40


def test_preferences_and_snapshots_survive_reopening(store):
    store.preferences({"CRYSTAL_QR_PROVIDER": "python"})
    store.snapshot("chamados", {"rows": [{"cte": "2-10-10402"}]})
    store.close()
    reopened = OperationsStore(store.path)
    reopened.initialize()
    try:
        assert reopened.preferences()["CRYSTAL_QR_PROVIDER"] == "python"
        assert reopened.snapshot("chamados")["rows"][0]["cte"] == "2-10-10402"
    finally:
        reopened.close()


def test_run_and_events_are_persistent_and_interrupted_run_is_recovered(store):
    async def exercise():
        state = RunState(store)
        run = await state.start("pendentes", False)
        await EventBus(store=store).publish("Inicio", run_id=run.id, kind="run.started")
        restored = RunState(store)
        await restored.restore()
        assert (await restored.get()).status == "failed"
        assert store.events(run.id)[0]["message"] == "Inicio"

    asyncio.run(exercise())
