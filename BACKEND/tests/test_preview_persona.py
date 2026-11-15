from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services.preview_persona import finance_identity, restrict_finance_preview


def test_finance_identity_requires_explicit_development_profile(tmp_path, monkeypatch):
    settings = SimpleNamespace(backend_root=tmp_path / "BACKEND", storage_dir=tmp_path / "runtime")
    assert finance_identity(settings) is None
    monkeypatch.setenv("NOVELIS_PREVIEW_ROLE", "finance")
    with pytest.raises(RuntimeError):
        finance_identity(settings)
    settings.storage_dir = tmp_path / "runtime/dev-preview/finance-backend"
    settings.backend_root.mkdir()
    (settings.backend_root / "CONFIG.dev").write_text("DEVMODE=1")
    (settings.backend_root / "credentials.json").write_text("{}")
    identity = finance_identity(settings)()
    assert identity["windows_user"] == "PREVIA\\financeiro.teste"
    assert identity["classification"]["sector"]["code"] == "FIN"
    (tmp_path / ".automacao-novelis-install").touch()
    with pytest.raises(RuntimeError):
        finance_identity(settings)


def test_finance_preview_can_message_but_cannot_start_automation():
    app = FastAPI()
    restrict_finance_preview(app)

    @app.post("/api/hub/chat/rooms")
    @app.post("/api/hub/runs")
    def action():
        return {"ok": True}

    with TestClient(app) as client:
        assert client.post("/api/hub/chat/rooms").status_code == 200
        assert client.post("/api/hub/runs").status_code == 403
