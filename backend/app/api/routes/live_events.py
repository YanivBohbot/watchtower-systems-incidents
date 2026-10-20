"""Server-sent events: alerts pushed to the browser as the camera process raises them."""

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from app.api.dependencies import call_live_hub, current_user, get_hub

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/live/events", dependencies=[Depends(current_user)])
async def live_events(request: Request, hub=Depends(get_hub)):
    subscription = await run_in_threadpool(call_live_hub, hub.subscribe)

    async def stream():
        # Polls without blocking, so an open wall tab does not hold a worker thread.
        try:
            yield ": connected\n\n"
            idle = 0.0
            while not await request.is_disconnected():
                try:
                    event = subscription.get(timeout=0)
                except Exception:
                    log.warning("Live hub lost; closing the event stream", exc_info=True)
                    return  # the browser reconnects and reloads the alert list
                if event is None:
                    await asyncio.sleep(0.25)
                    idle += 0.25
                    if idle >= 15:
                        idle = 0.0
                        yield ": ping\n\n"
                    continue
                idle = 0.0
                yield f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"
        finally:
            subscription.close()

    return StreamingResponse(
        stream(), media_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"}
    )
