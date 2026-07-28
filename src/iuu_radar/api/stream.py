"""GET /api/stream: Server-Sent Events endpoint emitting new anomalies and keep-alives."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["stream"])


async def _event_generator(region: str) -> AsyncIterator[str]:
    """Yield SSE-formatted anomaly events from the pub/sub bus, plus periodic keep-alives."""
    raise NotImplementedError("Implement in Phase 6 using iuu_radar.events.bus")


@router.get("/stream")
def stream(region: str):
    """Stream newly flagged anomalies to the browser as Server-Sent Events."""
    raise NotImplementedError("Implement in Phase 6")
