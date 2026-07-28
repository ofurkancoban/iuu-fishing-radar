"""Shared input validation for API query parameters (section 11.4 of CLAUDE.md).

Every list endpoint bounds limit/offset/bbox/region so a caller cannot trigger
an expensive or unbounded query. Invalid input raises HTTPException(422) with
a generic message; details are not leaked beyond "which parameter is invalid".
"""

from __future__ import annotations

from fastapi import HTTPException

from iuu_radar.api.deps import MAX_BBOX_AREA_DEG2, MAX_LIMIT
from iuu_radar.config import load_regions


def validate_region(region: str) -> str:
    """Raise 422 if the region is not one of the configured regions."""
    if region not in load_regions():
        raise HTTPException(status_code=422, detail="Unknown region.")
    return region


def validate_limit(limit: int) -> int:
    """Raise 422 if limit is out of the allowed [1, MAX_LIMIT] range."""
    if not (1 <= limit <= MAX_LIMIT):
        raise HTTPException(status_code=422, detail=f"limit must be between 1 and {MAX_LIMIT}.")
    return limit


def validate_offset(offset: int) -> int:
    """Raise 422 if offset is negative."""
    if offset < 0:
        raise HTTPException(status_code=422, detail="offset must be non-negative.")
    return offset


def validate_bbox(bbox: str | None) -> tuple[float, float, float, float] | None:
    """Parse and bound-check a 'min_lon,min_lat,max_lon,max_lat' bbox string."""
    if bbox is None:
        return None

    parts = bbox.split(",")
    if len(parts) != 4:
        raise HTTPException(status_code=422, detail="bbox must have 4 comma-separated values.")

    try:
        min_lon, min_lat, max_lon, max_lat = (float(p) for p in parts)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="bbox values must be numeric.") from exc

    if not (-180 <= min_lon < max_lon <= 180 and -90 <= min_lat < max_lat <= 90):
        raise HTTPException(status_code=422, detail="bbox is out of valid coordinate range.")

    area = (max_lon - min_lon) * (max_lat - min_lat)
    if area > MAX_BBOX_AREA_DEG2:
        raise HTTPException(status_code=422, detail="bbox area exceeds the allowed maximum.")

    return min_lon, min_lat, max_lon, max_lat
