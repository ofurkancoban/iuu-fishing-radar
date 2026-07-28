"""GET /api/hotspots?region=&bbox=."""

from __future__ import annotations

import duckdb
from fastapi import APIRouter, Depends

from iuu_radar.api.deps import get_read_only_connection
from iuu_radar.api.validation import validate_bbox, validate_region

router = APIRouter(prefix="/api/hotspots", tags=["hotspots"])


@router.get("")
def list_hotspots(
    region: str,
    bbox: str | None = None,
    conn: duckdb.DuckDBPyConnection = Depends(get_read_only_connection),
) -> list[dict]:
    """Return H3 hotspot cells with intensity, bounded by an optional bbox.

    For dense display, clients should prefer the PMTiles layer over this endpoint.
    """
    validate_region(region)
    parsed_bbox = validate_bbox(bbox)

    rows = conn.execute(
        "SELECT h3_cell, region, intensity FROM result_hotspots WHERE region = ?",
        [region],
    ).fetchall()

    if parsed_bbox is not None:
        import h3

        min_lon, min_lat, max_lon, max_lat = parsed_bbox
        filtered = []
        for h3_cell, r, intensity in rows:
            lat, lon = h3.cell_to_latlng(h3_cell)
            if min_lon <= lon <= max_lon and min_lat <= lat <= max_lat:
                filtered.append((h3_cell, r, intensity))
        rows = filtered

    return [{"h3_cell": r[0], "region": r[1], "intensity": r[2]} for r in rows]
