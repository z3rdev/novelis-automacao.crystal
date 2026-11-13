"""Opt-in integration against the real isolated offline installation fixture."""
import importlib.util
import json
import os
import socket
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(not os.environ.get("NOVELIS_TEST_INSTALLED_HUB"), reason="Requires isolated installed fixture")
def test_installed_api_starts_once_and_stops_its_own_process_tree(monkeypatch):
    root = Path(os.environ["NOVELIS_TEST_INSTALLED_HUB"]).resolve()
    assert root.is_relative_to((ROOT / "runtime/crystal-tests").resolve())
    assert root.parent.name.startswith("hub-offline-")
    spec = importlib.util.spec_from_file_location("installed_launcher", ROOT / "scripts/setup/launch_backend.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("NOVELIS_SQLITE_PATH", str(root / "runtime/isolated.sqlite"))
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    process = module.launch(root, port)
    assert process is not None
    try:
        assert module.launch(root, port) is None
        assert module.hub_ready(port)
        assert module.valid_health(module.health(port), root)
    finally:
        module.stop_backend(process)
    with socket.socket() as sock:
        assert sock.connect_ex(("127.0.0.1", port)) != 0
    (root.parent / "launcher-verification.json").write_text(json.dumps({
        "status": "succeeded", "port": port, "api_started": True,
        "second_launch_reused_api": True, "process_tree_stopped": True,
        "production_ready": False,
    }, indent=2))


@pytest.mark.skipif(not os.environ.get("NOVELIS_TEST_INSTALLED_HUB"), reason="Requires isolated installed fixture")
@pytest.mark.parametrize("configured", [False, True])
def test_real_api_readiness_with_and_without_database(monkeypatch, configured):
    root = Path(os.environ["NOVELIS_TEST_INSTALLED_HUB"]).resolve()
    assert root.is_relative_to((ROOT / "runtime/crystal-tests").resolve())
    spec = importlib.util.spec_from_file_location("real_readiness", ROOT / "scripts/setup/verify_backend.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("NOVELIS_SQLITE_PATH", str(root / "runtime/isolated.sqlite") if configured else "")
    folder = ROOT / "runtime/crystal-tests/hub-r2-readiness"
    folder.mkdir(exist_ok=True)
    name = "configured" if configured else "without-database"
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with (folder / (name + ".log")).open("w", encoding="utf-8") as log:
        process = module.start_backend(root, port, log)
        try:
            if configured:
                assert module.wait_ready(root, port, process, timeout=30)["status"] == "ok"
                record = {"status": "succeeded", "hub_api": True}
            else:
                with pytest.raises(module.ReadinessError) as caught:
                    module.wait_ready(root, port, process, timeout=30)
                assert caught.value.reason == "operational_database_unconfigured"
                assert caught.value.checks["api_responded"] is True
                assert caught.value.checks["hub_http_status"] == 503
                record = {"status": "expected_failure_reproduced", "reason": caught.value.reason,
                          "checks": caught.value.checks}
        finally:
            module.stop_backend(process)
    assert "Application startup complete" in (folder / (name + ".log")).read_text(encoding="utf-8")
    (folder / (name + ".json")).write_text(json.dumps(record, indent=2))
