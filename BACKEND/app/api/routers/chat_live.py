import asyncio
import json
from contextlib import suppress

import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.domain.chat import ChatError

router = APIRouter(prefix="/hub/chat", tags=["chat-live"])


@router.websocket("/live")
async def relay(socket: WebSocket):
    origin = socket.headers.get("origin")
    if origin and origin not in socket.app.state.settings.cors_origins:
        await socket.close(code=4403)
        return
    await socket.accept()
    tasks = []
    try:
        frame = await asyncio.wait_for(socket.receive_json(), timeout=10)
        if not isinstance(frame, dict):
            raise TypeError("frame")
        audit = socket.app.state.session_audit
        actor = await asyncio.to_thread(audit.session, frame.get("session")) if audit else None
        if not actor:
            await socket.close(code=4401)
            return
        remote = socket.app.state.chat_remote
        profile = await asyncio.to_thread(remote.profile)
        if not profile:
            await socket.send_json({"type": "local"})
            await socket.close(code=1000)
            return
        url = profile["url"].replace("https://", "wss://", 1).replace("http://", "ws://", 1)
        async with websockets.connect(
            url + "/api/hub/chat/live",
            open_timeout=10,
            max_size=65536,
            ping_interval=20,
            ping_timeout=20,
        ) as upstream:
            await upstream.send(json.dumps(remote.websocket_auth(actor)))

            async def downstream():
                async for message in upstream:
                    await socket.send_text(message)

            async def commands():
                while True:
                    value = await socket.receive_text()
                    if len(value) > 16000:
                        await socket.close(code=1009)
                        return
                    if not await asyncio.to_thread(audit.session, frame.get("session")):
                        await socket.close(code=4401)
                        return
                    await upstream.send(value)

            tasks = [asyncio.create_task(downstream()), asyncio.create_task(commands())]
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    except (
        OSError,
        TimeoutError,
        ValueError,
        TypeError,
        ChatError,
        WebSocketDisconnect,
        websockets.WebSocketException,
    ):
        with suppress(RuntimeError, WebSocketDisconnect):
            await socket.close(code=1011)
    finally:
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
