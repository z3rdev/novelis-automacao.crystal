"""Network authentication failures must be recoverable without exposing credentials."""
import ctypes
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]


def helper(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/setup/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def denied(code=1326):
    error = OSError("SYNTHETIC_PASSWORD_MUST_NOT_LEAK")
    error.winerror = code
    return error


def test_existing_access_uses_current_windows_identity_without_prompt(tmp_path, monkeypatch):
    module = helper("network_access")
    monkeypatch.setenv("NOVELIS_SQLITE_PATH", str(tmp_path / "shared.sqlite"))
    assert module.ensure_database_access(tmp_path, interactive=True) == {
        "configured": True, "folder_accessible": True, "credential_prompted": False}


def test_relative_database_is_resolved_from_backend_working_directory(tmp_path, monkeypatch):
    module = helper("network_access")
    (tmp_path / "BACKEND").mkdir()
    (tmp_path / "runtime").mkdir()
    monkeypatch.setenv("NOVELIS_SQLITE_PATH", "../runtime/database.sqlite")
    assert module.ensure_database_access(tmp_path)["folder_accessible"]


def test_silent_authentication_failure_is_specific_and_redacted(tmp_path, monkeypatch):
    module = helper("network_access")
    monkeypatch.setenv("NOVELIS_SQLITE_PATH", r"\\fixture\share\operations.sqlite")

    def refuse(_folder):
        raise denied()

    monkeypatch.setattr(module, "probe_folder", refuse)
    with pytest.raises(module.NetworkAccessError) as caught:
        module.ensure_database_access(tmp_path, interactive=False)
    assert caught.value.reason == "network_authentication_required"
    assert caught.value.checks == {"network_winerror": 1326}
    assert "SYNTHETIC_PASSWORD" not in str(caught.value)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows UNC authentication")
def test_interactive_authentication_uses_exact_share_and_rechecks_folder(tmp_path, monkeypatch):
    module = helper("network_access")
    monkeypatch.setenv("NOVELIS_SQLITE_PATH", r"\\fixture\share\folder\operations.sqlite")
    calls = []

    def probe(_folder):
        calls.append("probe")
        if len(calls) == 1:
            raise denied()

    def authenticate(share, check, code):
        assert share == r"\\fixture\share" and code == 1326
        check()
        return 0

    monkeypatch.setattr(module, "probe_folder", probe)
    monkeypatch.setitem(sys.modules, "windows_network", SimpleNamespace(authenticate_share=authenticate))
    assert module.ensure_database_access(tmp_path, interactive=True)["credential_prompted"]
    assert calls == ["probe", "probe"]


@pytest.mark.parametrize("code,reason", [(1219, "network_session_conflict"),
    (1223, "network_authentication_cancelled"), (53, "network_share_unavailable")])
def test_network_error_categories_do_not_expose_native_messages(tmp_path, monkeypatch, code, reason):
    module = helper("network_access")
    monkeypatch.setenv("NOVELIS_SQLITE_PATH", r"\\fixture\share\operations.sqlite")

    def refuse(_folder):
        raise denied(code)

    monkeypatch.setattr(module, "probe_folder", refuse)
    with pytest.raises(module.NetworkAccessError) as caught:
        module.ensure_database_access(tmp_path)
    assert caught.value.reason == reason
    assert "SYNTHETIC_PASSWORD" not in str(caught.value)


def test_native_prompt_clears_password_buffers_and_confirms_only_valid_access():
    module = helper("windows_network")
    buffers, confirmations = [], []

    def prompt(_info, _server, _context, _error, username, _ul, password, _pl, _save, _flags):
        username.value, password.value = "fixture\\operator", "SYNTHETIC_SECRET"
        buffers.extend([username, password])
        return 0

    def parse(_name, account, _al, domain, _dl):
        account.value, domain.value = "operator", "fixture"
        return 0

    def connect(_resource, password, account, _flags):
        assert password.value == "SYNTHETIC_SECRET" and account == "fixture\\operator"
        return 0

    module.windows_functions = lambda: (prompt, lambda server, valid: confirmations.append((server, valid)), parse, connect)
    assert module.authenticate_share(r"\\fixture\share", lambda: None, 1326) == 0
    assert confirmations == [("fixture", True)]
    assert all(not buffer.value for buffer in buffers)
    assert all(ctypes.string_at(ctypes.addressof(buffer), ctypes.sizeof(buffer)) == b"\0" * ctypes.sizeof(buffer)
               for buffer in buffers)


def test_native_failed_credentials_are_unconfirmed_and_password_buffer_cleared():
    module = helper("windows_network")
    passwords, confirmations = [], []

    def prompt(_i, _s, _c, _e, _u, _ul, password, _pl, _save, _flags):
        password.value = "SYNTHETIC_SECRET"
        passwords.append(password)
        return 0

    module.windows_functions = lambda: (prompt, lambda _s, valid: confirmations.append(valid),
        lambda *_args: 0, lambda *_args: 1326)
    assert module.authenticate_share(r"\\fixture\share", lambda: None, 1326) == 1326
    assert confirmations == [False, False, False]
    assert all(not password.value for password in passwords)


def test_preflight_failure_is_recorded_before_any_backend_process_starts(tmp_path, monkeypatch):
    module = helper("verify_backend")
    network = helper("network_access")
    monkeypatch.setattr(module, "start_backend", lambda *_args: pytest.fail("Backend cannot start before authentication"))

    def fail(*_args, **_kwargs):
        raise network.NetworkAccessError("network_authentication_required", 1326)

    monkeypatch.setattr(module, "ensure_database_access", fail)
    with pytest.raises(RuntimeError, match="network_authentication_required"):
        module.verify(tmp_path)
    result = json.loads((tmp_path / "runtime/backend-readiness.json").read_text())
    assert result["reason"] == "network_authentication_required"
    assert result["checks"]["network_winerror"] == 1326
    assert (tmp_path / "runtime/backend-preparation-message.txt").is_file()
