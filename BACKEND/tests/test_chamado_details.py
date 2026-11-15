from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers.hub import router
from app.services.chamado_details import detail_view, ticket_url


def config(base="https://novelis.example/portal/chamado/"):
    return SimpleNamespace(novelis=lambda: {"chamadoDiretoUrl": base})


@pytest.mark.parametrize("number", [None, "", "../../etc", "123?redirect=https://bad.example", "1234/5"])
def test_does_not_make_links_with_invalid_ticket_numbers(number):
    assert ticket_url(number, config()) is None


@pytest.mark.parametrize("base", ["file:///portal/chamado/", "javascript:alert(1)", "https://user:password@example/portal/chamado/", "https://example/other/"])
def test_requires_a_portal_http_route_without_embedded_credentials(base):
    assert ticket_url("202611140001", config(base)) is None


def test_detail_is_whitelisted_and_distinguishes_source_status_from_sync_time():
    value = detail_view({"id": "fixture-id", "chave": "1" * 44,
        "updated_at": datetime(2026, 11, 14, 12, tzinfo=UTC),
        "raw_payload": {"cte": "2-10-123", "chamado": "202611140001", "andamento": "Em análise",
                        "responsavel": "Operador", "PRIVATE_PASS": "must-not-be-forwarded"}}, config())
    assert value["portalUrl"] == "https://novelis.example/portal/chamado/202611140001"
    assert value["statusOriginal"] == "Em análise" and value["andamento"] == "em_analise"
    assert value["sincronizadoEm"] == "2026-11-14T12:00:00+00:00"
    assert value["chave"] == "1" * 44
    assert "must-not-be-forwarded" not in str(value)


def test_detail_endpoint_requires_session_and_handles_missing_record():
    app = FastAPI()
    catalog = SimpleNamespace(detail=Mock(return_value=None))
    app.state.hub = SimpleNamespace(store=SimpleNamespace(ready=True), chamados_catalog=catalog)
    app.state.session_audit = SimpleNamespace(session=lambda key: {"id": key} if key == "fixture-session" else None)
    app.include_router(router, prefix="/api")
    with TestClient(app) as client:
        assert client.get("/api/hub/chamados/unknown").status_code == 401
        assert client.get("/api/hub/chamados/unknown", headers={"X-Operator-Session": "fixture-session"}).status_code == 404
        catalog.detail.assert_called_once_with("unknown")
