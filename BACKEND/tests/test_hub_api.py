import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers.hub import router
from app.domain.run_state import RunState
from app.infrastructure.event_bus import EventBus
from app.infrastructure.operations_store import OperationsStore
from app.services.hub_service import HubService


class FakeAutomation:
    def __init__(self, store):
        self.state = RunState(store)
        self.events = EventBus(store=store)
        self.requests = []

    async def current(self):
        return await self.state.get()

    async def start(self, request):
        run = await self.state.start(request.flow, request.dry_run)
        self.requests.append(request)
        await self.events.publish("Inicio", kind="run.started", run_id=run.id,
                                  payload=request.model_dump(mode="json"))

    async def stop(self):
        await self.state.update(status="cancelled")


class FakeConfig:
    def __init__(self):
        self.values = {}

    def novelis(self):
        return {}

    def get(self, key):
        return self.values.get(key, "")


@pytest.fixture
def setup(tmp_path):
    settings = SimpleNamespace(backend_root=tmp_path / "BACKEND")
    settings.backend_root.mkdir()
    source = tmp_path / "captures/pendentes/latest-python.json"
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps({"generatedAt": "2026-11-11T12:00:00Z",
        "checked": [{"cte": "2-10-10402", "row": {"filial": 2, "serie": 10, "documento": 10402},
                     "evidence": {}}], "faltandoPdf": ["2-10-10402"]}), encoding="utf-8")
    store = OperationsStore(tmp_path / "novelischamado.sqlite")
    store.initialize()
    automation = FakeAutomation(store)
    hub = HubService(settings, FakeConfig(), store, automation, automation.events)
    app = FastAPI()
    app.state.hub = hub
    app.state.preview_browser = SimpleNamespace(state=lambda: {"open": False, "urls": []})
    app.include_router(router, prefix="/api")
    with TestClient(app) as client:
        yield client, hub, automation, source
    store.close()


def test_real_http_contract_and_persistent_snapshot_fallback(setup):
    client, hub, _, source = setup
    assert client.get("/api/hub/health/ping").status_code == 200
    ctes = client.get("/api/hub/ctes").json()
    assert ctes[0]["pdf"] == "faltando"
    assert ctes[0]["valor"] is None
    source.unlink()
    assert client.get("/api/hub/ctes").json() == ctes
    assert client.get("/api/hub/overview").json()["pdfFaltando"] == 1
    hub.store.snapshot("chamados", {"rows": [{"cte": "2-10-10402", "vlrTotal": 123.45,
                                               "aberturaNovelis": "SOLUCIONADO"}]})
    rows = client.get("/api/hub/chamados").json()
    assert rows[0]["valorTotal"] == 123.45
    assert rows[0]["andamento"] == "solucionado"


def test_batch_deduplicates_and_rejects_a_second_clients_start(setup):
    client, _, automation, _ = setup
    body = {"flow": "somente_pdf", "ctes": ["02-10-10402", "2-10-10402", "11-10-397"]}
    response = client.post("/api/hub/runs", json=body)
    assert response.status_code == 200
    assert response.json()["flow"] == "somente_pdf"
    assert automation.requests[0].manual_ctes == "2-10-10402\n11-10-397"
    assert automation.requests[0].execution_scope == "pdf"
    assert automation.requests[0].sample_cte == ""
    assert client.post("/api/hub/runs", json=body).status_code == 409
    assert len(automation.requests) == 1
    assert client.post("/api/hub/runs/current/stop").json()["state"] == "cancelada"


def test_invalid_batch_cannot_accidentally_start_an_unfiltered_run(setup):
    client, _, automation, _ = setup
    for ctes in [["abc"], ["2-10-10402", "invalid"], ["../../secrets"], ["0-10-10402"], ["2-10-0"]]:
        assert client.post("/api/hub/runs", json={"ctes": ctes}).status_code == 422
    assert client.post("/api/hub/runs", json={"periodoDias": 91}).status_code == 422
    assert client.post("/api/hub/documents/dacte/generate",
                       json={"ctes": ["2-10-10402"], "metodo": "xml"}).status_code == 422
    assert automation.requests == []


def test_xml_list_uses_sql_enrichment_and_pending_batch_without_a_single_cte_filter(setup):
    client, _, automation, _ = setup
    response = client.post("/api/hub/runs", json={"flow": "somente_xml", "ctes": ["2-10-10402", "11-10-397"]})
    assert response.status_code == 200
    assert response.json()["flow"] == "somente_xml"
    request = automation.requests[0]
    assert request.flow == "pendentes" and request.execution_scope == "xml"
    assert request.manual_ctes == "2-10-10402\n11-10-397" and request.sample_cte == ""


def test_pdf_lookup_stays_stable_when_new_jobs_arrive(setup, tmp_path):
    client, hub, _, _ = setup
    pdf = tmp_path / "first.pdf"
    pdf.write_bytes(b"%PDF-1.4\nfirst document\n")

    def saved(cte, path):
        hub.store.add_event({"kind": "crystal_pdf.saved", "run_id": "batch", "message": "Salvo",
            "level": "info", "created_at": "2026-11-11T12:00:00Z", "payload": {"cte": cte, "pdfFile": str(path)}})

    saved("2-10-10402", pdf)
    first_id = client.get("/api/hub/documents/dacte/jobs").json()[0]["id"]
    saved("11-10-397", tmp_path / "other.pdf")
    response = client.get(f"/api/hub/documents/dacte/file/{first_id}")
    assert response.status_code == 200
    assert response.content == pdf.read_bytes()
    assert client.get("/api/hub/documents/dacte/file/unknown").status_code == 404


def test_config_is_whitelisted_persistent_and_no_browser_is_started(setup):
    client, hub, _, _ = setup
    assert client.get("/api/hub/automation/browser").json()["ativo"] is False
    response = client.put("/api/hub/config", json=[{"fields": [
        {"key": "NOVELIS_SQLITE_PATH", "value": "elsewhere.sqlite"},
        {"key": "DB_PASSWORD", "value": "must-not-be-saved"},
        {"key": "CRYSTAL_QR_PROVIDER", "value": "python"}]}])
    assert response.status_code == 200
    assert hub.store.preferences() == {"CRYSTAL_QR_PROVIDER": "python"}
    assert client.put("/api/hub/automation/steps", json=[]).status_code == 409
    assert client.get("/api/hub/logs?since=bad").status_code == 422


def test_monitor_shows_and_focuses_the_parallel_sefaz_browser(setup):
    client, _, _, _ = setup
    child = SimpleNamespace(state=lambda: {"open": True, "urls": ["https://www.cte.fazenda.gov.br"]},
                            snapshot=AsyncMock(return_value={"url": "https://www.cte.fazenda.gov.br", "image": "data:image/jpeg;base64,AA=="}),
                            page=object(), focus_page=AsyncMock())
    client.app.state.preview_browser = SimpleNamespace(preview_driver=lambda: child)
    frame = client.get("/api/hub/automation/browser").json()
    assert frame["ativo"] and "fazenda.gov.br" in frame["url"]
    assert client.post("/api/hub/automation/browser/focus").status_code == 200
    child.focus_page.assert_awaited_once_with(child.page)


def test_unconfigured_store_returns_clear_error():
    app = FastAPI()
    app.state.hub = None
    app.include_router(router, prefix="/api")
    with TestClient(app) as client:
        assert client.get("/api/hub/health/ping").status_code == 503
