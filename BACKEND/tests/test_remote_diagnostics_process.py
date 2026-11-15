import asyncio
import json
from types import SimpleNamespace
from unittest.mock import Mock

from app.domain.remote_diagnostics import DiagnosticOptions
from app.services.remote_diagnostics import process as module


def test_timeout_preserves_checkpoint_and_stops_only_owned_process(monkeypatch, tmp_path):
    stopped = Mock()
    monkeypatch.setattr(module, "stop_tree", stopped)
    monkeypatch.setattr(
        module.psutil, "Process", lambda pid: SimpleNamespace(create_time=lambda: 123.0)
    )
    captured = {}

    async def run():
        done = asyncio.Event()
        process = SimpleNamespace(pid=43210, returncode=None, stdout=asyncio.StreamReader())
        process.stdout.feed_data(
            module.FRAME
            + json.dumps({"schema_version": 1, "complete": False, "checks": []}).encode()
            + b"\n"
        )

        async def wait():
            await done.wait()

        def kill():
            process.returncode = -1
            done.set()

        process.wait, process.kill = wait, kill

        async def spawn(*args, **kwargs):
            captured.update(args=args, kwargs=kwargs)
            return process

        monkeypatch.setattr(module.asyncio, "create_subprocess_exec", spawn)
        settings = SimpleNamespace(
            backend_root=tmp_path, storage_dir=tmp_path, novelis_sqlite_path=None
        )
        result = await module.ProbeRunner(settings, timeout=0.01).collect(DiagnosticOptions())
        assert result["complete"] is False and result["incomplete_reason"] == "probe_timeout"

    asyncio.run(run())
    stopped.assert_called_once_with(43210, 123.0)
    args = captured["args"]
    assert args[1:4] == ("-I", "-m", "app.services.remote_diagnostics.probe")
    assert "shell" not in captured["kwargs"]
    assert "PYTHONPATH" not in captured["kwargs"]["env"]


def test_pid_reuse_does_not_kill_unrelated_process(monkeypatch):
    foreign = SimpleNamespace(create_time=lambda: 200.0, children=Mock(), kill=Mock())
    monkeypatch.setattr(module.psutil, "Process", lambda pid: foreign)
    module.stop_tree(43210, 123.0)
    foreign.children.assert_not_called()
    foreign.kill.assert_not_called()
