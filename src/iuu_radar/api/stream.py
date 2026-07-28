"""GET /api/stream: Server-Sent Events endpoint emitting new anomalies and keep-alives.

Caddy must not buffer this route (see caddy/Caddyfile in Phase 8) or events
will not reach the browser as they are published.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from iuu_radar.api.deps import get_settings
from iuu_radar.api.validation import validate_region
from iuu_radar.config import Settings
from iuu_radar.events.bus import get_event_bus

router = APIRouter(prefix="/api", tags=["stream"])

KEEPALIVE_SECONDS = 15


async def _event_generator(region: str, settings: Settings) -> AsyncIterator[dict]:
    """Yield SSE-formatted anomaly events from the pub/sub bus, plus periodic keep-alives."""
    bus = get_event_bus(settings)
    subscription = bus.subscribe(region)

    while True:
        try:
            anomaly = await asyncio.wait_for(subscription.__anext__(), timeout=KEEPALIVE_SECONDS)
        except TimeoutError:
            yield {"event": "keep-alive", "data": ""}
            continue
        except StopAsyncIteration:
            return
        yield {"event": "anomaly", "data": json.dumps(anomaly)}


@router.get("/stream")
def stream(region: str, settings: Settings = Depends(get_settings)) -> EventSourceResponse:
    """Stream newly flagged anomalies to the browser as Server-Sent Events."""
    validate_region(region)
    return EventSourceResponse(_event_generator(region, settings))
