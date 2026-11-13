"""LAN entry point for Cargo Hub; legacy administrative routes stay private."""

from fastapi import Request
from fastapi.responses import JSONResponse

from app.main import app

app.state.legacy_config.values["RODOPAR_BROWSER_ENABLED"] = "false"


@app.middleware("http")
async def central_routes(request: Request, call_next):
    path = request.url.path
    if not path.startswith("/api/hub/") and path != "/api/health":
        return JSONResponse({"detail": "Rota indisponivel no backend central."}, status_code=404)
    return await call_next(request)
