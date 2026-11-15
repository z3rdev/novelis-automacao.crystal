import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.domain.remote_diagnostics import DiagnosticOptions, DiagnosticRequest
from app.infrastructure.operations_store import OperationsStore
from app.services.remote_diagnostics.history import collect_history, event_view, public_ticket_url
from app.services.remote_diagnostics.redaction import Redactor


@pytest.fixture
def redactor():
    return Redactor(
        SimpleNamespace(values={"SQL_PASS": "fixture-secret-2026", "PIDKEY": "fixture-license"})
    )


def test_redaction_removes_secrets_but_keeps_boolean_diagnostic_metadata(redactor):
    result = redactor.clean(
        {
            "message": "fixture-secret-2026 fixture-license password='a secret' Bearer abc.def ghi "
            "postgresql://user:pwd@host/db eyJabc.def.ghi "
            "-----BEGIN PRIVATE KEY-----hidden-----END PRIVATE KEY-----",
            "Authorization": "Bearer hidden",
            "private_key_exported": False,
            "stored_credentials": True,
            "nested": {"password": "hidden"},
        }
    )
    text = json.dumps(result)
    for secret in (
        "fixture-secret-2026",
        "fixture-license",
        "a secret",
        "abc.def",
        "user:pwd",
        "eyJabc",
        "hidden",
    ):
        assert secret not in text
    assert result["private_key_exported"] is False and result["stored_credentials"] is True


def test_http_evidence_is_allowlisted_and_does_not_turn_http_200_into_confirmation(redactor):
    item = event_view(
        {
            "kind": "novelis.save",
            "run_id": "r1",
            "level": "info",
            "payload": {
                "cte": "1-10-100",
                "save_http": 200,
                "readback_http": 403,
                "status": "unconfirmed",
                "request_headers": {"Cookie": "hidden"},
                "response_body": "hidden",
                "attachments": [r"C:\private\CTE.xml"],
                "url": "https://novelis.wtmh.com.br/portal/chamado/123?token=hidden",
                "ticket": {"numero": "123", "password": "hidden"},
                "result": {"ok": False, "body": "hidden"},
            },
        },
        redactor,
    )
    assert item["details"]["status"] == "unconfirmed"
    assert item["details"]["save_http"] == 200
    assert item["details"]["attachments"] == ["CTE.xml"]
    assert item["details"]["url"] == "https://novelis.wtmh.com.br/portal/chamado/123"
    assert "hidden" not in json.dumps(item)
    assert public_ticket_url("https://evil.example/portal/chamado/123") == ""


def test_history_is_machine_scoped_time_bounded_and_keeps_failed_runs(tmp_path, redactor):
    store = OperationsStore(tmp_path / "operations.sqlite", machine_id="this-pc")
    store.initialize()
    now = datetime.now(UTC)
    for identifier, machine, days in (
        ("recent", "this-pc", 0),
        ("foreign", "other-pc", 0),
        ("old", "this-pc", 8),
    ):
        writer = OperationsStore(store.path, machine_id=machine)
        writer.save_run(
            {
                "id": identifier,
                "status": "failed",
                "flow": "pendentes",
                "started_at": (now - timedelta(days=days)).isoformat(),
                "message": "Falhou",
            }
        )
        writer.add_event(
            {
                "run_id": identifier,
                "kind": "novelis.save",
                "level": "error",
                "created_at": now.isoformat(),
                "message": "Falha HTTP",
                "payload": {"save_http": 403},
            }
        )
    history = collect_history(store, DiagnosticOptions(days_back=7, max_runs=5), redactor)
    assert [run["id"] for run in history["runs"]] == ["recent"]
    assert history["runs"][0]["status"] == "failed"
    assert history["http"][0]["details"]["save_http"] == 403
    assert history["http"][0]["details"]["run_id"] == "recent"


@pytest.mark.parametrize(
    "values", [{"max_runs": 21}, {"days_back": 31}, {"command": "whoami"}, {"max_runs": 0}]
)
def test_options_reject_commands_and_unbounded_collection(values):
    with pytest.raises(ValueError):
        DiagnosticOptions.model_validate(values)
    with pytest.raises(ValueError):
        DiagnosticRequest.model_validate({"device_id": "not-a-uuid"})
