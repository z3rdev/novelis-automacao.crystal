"""Explicit, development-only Finance identity for two-window messaging tests."""

import os

from fastapi.responses import JSONResponse

from app.services.device_classification import classify_computer_name
from app.services.releases.config import DeveloperConfig


def finance_identity(settings):
    if os.environ.get("NOVELIS_PREVIEW_ROLE") != "finance":
        return None
    expected = settings.backend_root.parent / "runtime/dev-preview/finance-backend"
    if (
        settings.storage_dir.resolve() != expected.resolve()
        or not DeveloperConfig(settings.backend_root).enabled()
        or (settings.backend_root.parent / ".automacao-novelis-install").exists()
    ):
        raise RuntimeError(
            "A identidade de teste Financeiro exige a prévia local de desenvolvimento."
        )
    return lambda: {
        "windows_user": "PREVIA\\financeiro.teste",
        "computer_name": "NB-FIN-VIN-TESTE",
        "mac_addresses": [],
        "classification": classify_computer_name("NB-FIN-VIN-TESTE"),
    }


def restrict_finance_preview(app):
    @app.middleware("http")
    async def chat_only(request, call_next):
        path = request.url.path
        allowed = path == "/api/hub/session" or path.startswith("/api/hub/chat/")
        if request.method not in {"GET", "HEAD", "OPTIONS"} and not allowed:
            return JSONResponse(
                {"detail": "Esta prévia do Financeiro está limitada ao teste de mensagens e GNRE."},
                status_code=403,
            )
        return await call_next(request)
