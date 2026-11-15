from fastapi import APIRouter

from app.api.routers import (
    browser,
    capture_files,
    chamados,
    config,
    events,
    flows,
    health,
    hub,
    mappings,
    overlay,
    pendentes,
    reports,
    runs,
    sessions,
    steps,
    updates,
    operator_features,
    message_configuration,
    master_access,
    tariffs,
    execution_reports,
    developer_diagnostics,
    chat,
)


api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(hub.router)
api_router.include_router(sessions.router)
api_router.include_router(updates.router)
api_router.include_router(operator_features.router)
api_router.include_router(config.router)
api_router.include_router(chamados.router)
api_router.include_router(steps.router)
api_router.include_router(flows.router)
api_router.include_router(mappings.router)
api_router.include_router(runs.router)
api_router.include_router(overlay.router)
api_router.include_router(browser.router)
api_router.include_router(events.router)
api_router.include_router(pendentes.router)
api_router.include_router(capture_files.router)
api_router.include_router(reports.router)

api_router.include_router(message_configuration.router)
api_router.include_router(master_access.router)
api_router.include_router(tariffs.router)
api_router.include_router(execution_reports.router)
api_router.include_router(developer_diagnostics.router)
api_router.include_router(chat.router)
