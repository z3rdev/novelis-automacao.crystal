"""Real loopback responses must explain readiness failures without exposing secrets."""
import importlib.util
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import request

import pytest

ROOT = Path(__file__).resolve().parents[2]


def helper():
    spec = importlib.util.spec_from_file_location("readiness_fixture", ROOT / "scripts/setup/verify_backend.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def local_api(tmp_path):
    (tmp_path / "DESKTOP/automacao_novelis_desktop").mkdir(parents=True)
    (tmp_path / "DESKTOP/automacao_novelis_desktop/config.py").write_text('APP_VERSION = "0.1.34"')
    (tmp_path / "BACKEND").mkdir()
    state = {"hub_status": 200, "version": "0.1.34", "hits": []}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            state["hits"].append(self.path)
            basic = self.path == "/api/health"
            data = ({"status": "ok", "service": "automacao-novelis-backend", "version": state["version"],
                "playwrightDriverOk": True, "backendRoot": str(tmp_path / "BACKEND")} if basic else {"versao": "0.1.34"})
            self.send_response(200 if basic else state["hub_status"])
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield tmp_path, server.server_port, state
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


class Alive:
    def poll(self):
        return None


def test_ready_api_is_reached_directly_despite_inherited_proxy(local_api, monkeypatch):
    root, port, state = local_api
    module = helper()
    # Force proxy handling as on a Windows proxy configuration lacking bypass.
    monkeypatch.setattr(request, "getproxies", lambda: {"http": "http://127.0.0.1:1"})
    monkeypatch.setattr(request, "proxy_bypass", lambda _host: False)
    data = module.wait_ready(root, port, Alive(), timeout=3)
    assert data["version"] == "0.1.34"
    assert state["hits"] == ["/api/health", "/api/hub/health/ping"]


def test_started_api_without_operational_database_reports_hub_503(local_api):
    root, port, state = local_api
    state["hub_status"] = 503
    module = helper()
    started = time.monotonic()
    with pytest.raises(module.ReadinessError) as caught:
        module.wait_ready(root, port, Alive(), timeout=3)
    assert caught.value.reason == "operational_database_unconfigured"
    assert caught.value.checks["api_responded"] is True
    assert caught.value.checks["api_http_status"] == 200
    assert caught.value.checks["hub_http_status"] == 503
    assert time.monotonic() - started < 2


def test_wrong_version_is_not_accepted_as_ready(local_api):
    root, port, state = local_api
    state["version"] = "0.1.0"
    module = helper()
    with pytest.raises(module.ReadinessError, match="backend_identity_or_driver_mismatch"):
        module.wait_ready(root, port, Alive(), timeout=3)
    assert state["hits"] == ["/api/health"]


def test_failed_verification_records_safe_reason_and_http_status(tmp_path, monkeypatch):
    module = helper()
    secret = "SYNTHETIC_CREDENTIAL_MUST_NOT_APPEAR"
    monkeypatch.setenv("HTTP_PROXY", f"http://user:{secret}@127.0.0.1:1")
    monkeypatch.setattr(module, "start_backend", lambda *_args: Alive())
    monkeypatch.setattr(module, "stop_backend", lambda _process: None)

    def refuse(*_args):
        raise module.ReadinessError("operational_database_unconfigured",
            {"api_responded": True, "api_http_status": 200, "hub_http_status": 503})

    monkeypatch.setattr(module, "wait_ready", refuse)
    with pytest.raises(RuntimeError, match="operational_database_unconfigured"):
        module.verify(tmp_path)
    text = (tmp_path / "runtime/backend-readiness.json").read_text()
    report = json.loads(text)
    assert report["reason"] == "operational_database_unconfigured"
    assert report["checks"]["hub_http_status"] == 503
    assert report["status"] == "failed"
    assert secret not in text
