import asyncio
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI, WebSocket

from app.api.operator_session import require_operator_session
from app.api.routers.chat import router
from app.chat_server.auth import ClientRegistry, central_actor
from app.chat_server.config import ServerConfig
from app.chat_server.realtime import ChatRealtime, serve_socket
from app.chat_server.service import CentralChatService
from app.services.chat_archive import ChatArchive


def create_server(config=None, service=None, registry=None):
    config = config or ServerConfig()
    root = Path(__file__).resolve().parents[2]
    service = service or CentralChatService(SimpleNamespace(backend_root=root), config)
    registry = registry or ClientRegistry(
        os.environ.get("CHAT_CLIENTS_FILE", "/run/secrets/chat-clients")
    )
    realtime = ChatRealtime()

    def expired_documents():
        with service.store.connection() as db:
            return db.execute(
                "SELECT cte FROM public.cargo_hub_chat_documents WHERE archive_state='archived' AND expires_at<=now()"
            ).fetchall()

    async def maintenance():
        archive = ChatArchive(service, None)
        while True:
            try:
                await asyncio.to_thread(service.documents.files.objects.ensure_retention)
                rows = await asyncio.to_thread(expired_documents)
                for row in rows:
                    await asyncio.to_thread(archive.expire, row["cte"])
            except Exception:  # noqa: BLE001 - retry provider failures without logging secrets
                import logging

                logging.getLogger(__name__).warning("Retenção de GNRE aguardando nova tentativa.")
            await asyncio.sleep(60)

    @asynccontextmanager
    async def lifespan(app):
        await asyncio.to_thread(service.store.ensure)
        task = asyncio.create_task(maintenance())
        yield
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    app = FastAPI(title="Cargo Hub Chat", lifespan=lifespan)
    app.state.chat, app.state.chat_registry = service, registry
    app.state.chat_realtime = realtime
    app.dependency_overrides[require_operator_session] = central_actor
    app.include_router(router, prefix="/api")

    @app.middleware("http")
    async def notify_changes(request, call_next):
        response = await call_next(request)
        if request.method in {"POST", "PUT"} and response.status_code < 300:
            realtime.changed()
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/health")
    def health():
        with service.store.connection() as db:
            db.execute("SELECT 1")
        return {"status": "ok", "service": "cargo-hub-chat"}

    @app.websocket("/api/hub/chat/live")
    async def live(socket: WebSocket):
        await serve_socket(socket, service, registry, realtime)

    return app
