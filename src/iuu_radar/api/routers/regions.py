"""GET /api/regions."""

from __future__ import annotations

from fastapi import APIRouter

from iuu_radar.config import load_regions

router = APIRouter(prefix="/api/regions", tags=["regions"])


@router.get("")
def list_regions() -> list[dict]:
    """List every configured region with its display name and bbox.

    Lets the frontend discover which regions exist and where to fit the map,
    instead of hardcoding a single region.
    """
    return [
        {"region": key, "name": cfg["name"], "bbox": cfg["bbox"]}
        for key, cfg in load_regions().items()
    ]
