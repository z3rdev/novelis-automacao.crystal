import asyncio

from app.chat_server.realtime import ChatRealtime


def test_messages_are_pushed_only_to_authorized_room_subscribers():
    realtime = ChatRealtime()
    allowed, other = asyncio.Event(), asyncio.Event()
    inbox, blocked = asyncio.Queue(maxsize=1), asyncio.Queue(maxsize=1)
    realtime.connections[allowed] = ({"room-1"}, inbox)
    realtime.connections[other] = ({"room-2"}, blocked)
    message = {"id": "persisted"}
    realtime.changed("room-1", message)
    assert inbox.get_nowait() == {
        "type": "message.created",
        "room_id": "room-1",
        "message": message,
    }
    assert blocked.empty()
    assert allowed.is_set() and other.is_set()
    realtime.changed("room-1", message)
    realtime.changed("room-1", message)
    assert inbox.qsize() == 1
