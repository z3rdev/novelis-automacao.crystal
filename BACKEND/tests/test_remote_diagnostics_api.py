from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers.developer_diagnostics import router
from app.infrastructure.chamados_postgres import CommunicationUnavailable
from app.infrastructure.diagnostic_queue import DiagnosticTargetUnavailable


@pytest.fixture
def client(tmp_path):
    (tmp_path / "CONFIG.dev").write_text("DEVMODE=1")
    (tmp_path / "credentials.json").write_text("{}")
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.state.settings = SimpleNamespace(backend_root=tmp_path)
    app.state.session_audit = SimpleNamespace(
        session=lambda value: (
            {"windows_user": "DOMAIN\\dev"} if value == "fixture-session" else None
        )
    )
    app.state.diagnostic_queue = Mock()
    app.state.diagnostic_queue.agents.return_value = []
    with TestClient(app) as result:
        yield result, app.state.diagnostic_queue, tmp_path


HEADER = {"X-Operator-Session": "fixture-session"}
PATH = "/api/hub/developer/diagnostics"


@pytest.mark.parametrize("path", ["", "/agents", "/00000000-0000-0000-0000-000000000000"])
def test_all_reads_require_login_and_developer_mode(client, path):
    http, queue, root = client
    assert http.get(PATH + path).status_code == 401
    (root / "CONFIG.dev").unlink()
    assert http.get(PATH + path, headers=HEADER).status_code == 403
    assert not queue.mock_calls


def test_request_uses_windows_actor_and_only_typed_options(client):
    http, queue, _ = client
    identifier = str(uuid4())
    queue.create.return_value = {"id": str(uuid4()), "state": "queued"}
    response = http.post(
        PATH,
        headers=HEADER,
        json={"device_id": identifier, "options": {"max_runs": 5, "days_back": 1}},
    )
    assert response.status_code == 202
    queue.create.assert_called_once_with(identifier, "DOMAIN\\dev", {"max_runs": 5, "days_back": 1})
    queue.reset_mock()
    assert (
        http.post(
            PATH, headers=HEADER, json={"device_id": identifier, "options": {"command": "whoami"}}
        ).status_code
        == 422
    )
    assert http.post(PATH, json={"device_id": identifier}).status_code == 401
    assert not queue.mock_calls


@pytest.mark.parametrize(
    "exception,code",
    [(DiagnosticTargetUnavailable("secret"), 409), (CommunicationUnavailable("secret"), 503)],
)
def test_queue_errors_do_not_leak_connection_details(client, exception, code):
    http, queue, _ = client
    queue.create.side_effect = exception
    response = http.post(PATH, headers=HEADER, json={"device_id": str(uuid4())})
    assert response.status_code == code
    assert "secret" not in response.text


def test_missing_result_and_invalid_uuid(client):
    http, queue, _ = client
    queue.get.return_value = None
    assert http.get(PATH + "/" + str(uuid4()), headers=HEADER).status_code == 404
    assert http.get(PATH + "/bad-id", headers=HEADER).status_code == 422
