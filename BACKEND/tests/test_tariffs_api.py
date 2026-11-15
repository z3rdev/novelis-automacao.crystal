from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers.tariffs import router
from app.infrastructure.chamados_postgres import CommunicationUnavailable


def test_tariff_read_and_refresh_require_an_operator_and_validate_filters():
    app = FastAPI()
    app.state.session_audit = SimpleNamespace(
        session=lambda token: {"id": "fixture"} if token == "fixture" else None
    )
    app.state.tariffs = SimpleNamespace(page=lambda **q: {"rows": [], "query": q})
    app.include_router(router, prefix="/api")
    with TestClient(app) as client:
        assert client.get("/api/hub/tariffs").status_code == 401
        assert client.post("/api/hub/tariffs/sync").status_code == 401
        client.headers["X-Operator-Session"] = "fixture"
        result = client.get("/api/hub/tariffs?origin=1112&validity=vigente")
        assert result.status_code == 200 and result.json()["query"]["origin"] == "1112"
        assert client.get("/api/hub/tariffs?validity=arbitrary").status_code == 422
        assert client.get("/api/hub/tariffs?size=10000").status_code == 422
        assert client.get("/api/hub/tariffs?page=-1").status_code == 422

        def fail(**query):
            raise CommunicationUnavailable("fixture-private-driver-message")

        app.state.tariffs.page = fail
        result = client.get("/api/hub/tariffs")
        assert result.status_code == 503 and "fixture-private" not in result.text
