from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_event_bus
from app.infrastructure.event_bus import EventBus


router = APIRouter(prefix="/events", tags=["events"])


@router.get("")
async def stream_events(event_bus: EventBus = Depends(get_event_bus)) -> StreamingResponse:
    async def stream():
        async for event in event_bus.stream(include_history=True):
            yield (
                f"id: {event.id}\n"
                "event: automation\n"
                f"data: {event.model_dump_json()}\n\n"
            )

    return StreamingResponse(stream(), media_type="text/event-stream")
