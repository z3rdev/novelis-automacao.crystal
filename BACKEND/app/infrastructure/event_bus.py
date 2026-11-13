import asyncio
from collections import deque
from collections.abc import AsyncIterator
from typing import Any

from app.domain.models import AutomationEvent, EventLevel


class EventBus:
    def __init__(self, max_history: int = 300, store=None) -> None:
        self._counter = 0
        self._history: deque[AutomationEvent] = deque(maxlen=max_history)
        self._subscribers: set[asyncio.Queue[AutomationEvent]] = set()
        self._lock = asyncio.Lock()
        self.store = store

    async def publish(
        self,
        message: str,
        *,
        run_id: str | None = None,
        level: EventLevel = "info",
        kind: str = "event",
        payload: dict[str, Any] | None = None,
    ) -> AutomationEvent:
        async with self._lock:
            self._counter += 1
            event = AutomationEvent(
                id=self._counter,
                run_id=run_id,
                level=level,
                kind=kind,
                message=message,
                payload=payload or {},
            )
            if self.store:
                event.id = await asyncio.to_thread(self.store.add_event, event.model_dump(mode="json"))
            self._history.append(event)
            queues = list(self._subscribers)

        for queue in queues:
            await queue.put(event)
        return event

    async def history(self) -> list[AutomationEvent]:
        async with self._lock:
            return list(self._history)

    async def stream(self, include_history: bool = True) -> AsyncIterator[AutomationEvent]:
        queue: asyncio.Queue[AutomationEvent] = asyncio.Queue()
        async with self._lock:
            if include_history:
                for event in self._history:
                    queue.put_nowait(event)
            self._subscribers.add(queue)

        try:
            while True:
                yield await queue.get()
        finally:
            async with self._lock:
                self._subscribers.discard(queue)
