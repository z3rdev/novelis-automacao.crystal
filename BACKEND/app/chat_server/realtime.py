import asyncio
import hashlib
import json
from uuid import UUID

from fastapi import HTTPException, WebSocket, WebSocketDisconnect

from app.domain.chat import ChatError, ChatMessageInput
from app.infrastructure.chamados_postgres import CommunicationUnavailable


class ChatRealtime:
    def __init__(self):
        self.connections = {}

    def changed(self, room_id=None, message=None):
        for signal, (rooms, queue) in tuple(self.connections.items()):
            if message and str(room_id) in rooms and not queue.full():
                queue.put_nowait(
                    {"type": "message.created", "room_id": str(room_id), "message": message}
                )
            signal.set()


async def serve_socket(socket: WebSocket, service, registry, realtime):
    await socket.accept()
    try:
        frame = await asyncio.wait_for(socket.receive_json(), timeout=10)
        if not isinstance(frame, dict):
            raise TypeError("frame")
        actor = await asyncio.to_thread(
            registry.authenticate,
            frame.get("client_id"),
            frame.get("token"),
            frame.get("windows_user", ""),
            frame.get("computer_name", ""),
        )
    except (HTTPException, ValueError, TypeError, TimeoutError, WebSocketDisconnect):
        await socket.close(code=4401)
        return
    signal = asyncio.Event()
    rooms = set()
    queue = asyncio.Queue(maxsize=100)
    realtime.connections[signal] = (rooms, queue)
    send_lock = asyncio.Lock()

    async def send(value):
        async with send_lock:
            await socket.send_json(value)

    async def updates():
        previous = None
        while True:
            signal.clear()
            await asyncio.to_thread(
                registry.authenticate,
                frame.get("client_id"),
                frame.get("token"),
                actor["windows_user"],
                actor["computer_name"],
            )
            inbox = await asyncio.to_thread(service.inbox, actor)
            rooms.clear()
            rooms.update(room["id"] for room in inbox["rooms"])
            digest = hashlib.sha256(json.dumps(inbox, sort_keys=True).encode()).hexdigest()
            if digest != previous:
                await send({"type": "chat.changed", "revision": digest})
                previous = digest
            await send({"type": "ping"})
            try:
                await asyncio.wait_for(signal.wait(), timeout=10)
            except TimeoutError:
                pass

    async def commands():
        while True:
            frame = await socket.receive_json()
            if not isinstance(frame, dict):
                await send({"type": "error", "message": "Comando de chat inválido."})
                continue
            if frame.get("type") == "pong":
                continue
            if frame.get("type") != "message.send":
                await send({"type": "error", "message": "Comando de chat inválido."})
                continue
            try:
                body = ChatMessageInput(client_id=frame.get("client_id"), body=frame.get("body"))
                message = await asyncio.to_thread(service.send, actor, UUID(frame["room_id"]), body)
                await send(
                    {"type": "message.ack", "client_id": str(body.client_id), "message": message}
                )
                realtime.changed(frame["room_id"], message)
            except (ChatError, ValueError, KeyError) as error:
                await send(
                    {
                        "type": "error",
                        "message": str(error)
                        if isinstance(error, ChatError)
                        else "Mensagem inválida.",
                    }
                )

    async def messages():
        while True:
            await send(await queue.get())

    tasks = [
        asyncio.create_task(updates()),
        asyncio.create_task(commands()),
        asyncio.create_task(messages()),
    ]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        realtime.connections.pop(signal, None)
        for task in tasks:
            task.cancel()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        code = (
            1011 if any(isinstance(value, CommunicationUnavailable) for value in results) else 1000
        )
        try:
            await socket.close(code=code)
        except (RuntimeError, WebSocketDisconnect):
            pass
