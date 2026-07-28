"""GET /api/anomalies/latest?region=&limit=."""

from __future__ import annotations

import json

import duckdb
from fastapi import APIRouter, Depends

from iuu_radar.api.deps import get_read_only_connection
from iuu_radar.api.validation import validate_limit, validate_region

router = APIRouter(prefix="/api/anomalies", tags=["anomalies"])


@router.get("/latest")
def latest_anomalies(
    region: str,
    limit: int = 50,
    conn: duckdb.DuckDBPyConnection = Depends(get_read_only_connection),
) -> list[dict]:
    """Return the most recent flagged anomalies, used to seed the live feed's initial state."""
    validate_region(region)
    validate_limit(limit)

    rows = conn.execute(
        """
        SELECT id, region, vessel_id, lon, lat, ts, reasons
        FROM result_anomalies
        WHERE region = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        [region, limit],
    ).fetchall()

    return [
        {
            "id": r[0],
            "region": r[1],
            "vessel_id": r[2],
            "lon": r[3],
            "lat": r[4],
            "ts": r[5],
            "reasons": json.loads(r[6]),
        }
        for r in rows
    ]
