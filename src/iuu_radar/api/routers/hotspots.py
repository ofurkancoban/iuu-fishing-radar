"""GET /api/hotspots?region=&bbox=."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/hotspots", tags=["hotspots"])


@router.get("")
def list_hotspots(region: str, bbox: str | None = None) -> list[dict]:
    """Return H3 hotspot cells with intensity, bounded by an optional bbox.

    For dense display, clients should prefer the PMTiles layer over this endpoint.
    """
    raise NotImplementedError("Implement in Phase 6")
