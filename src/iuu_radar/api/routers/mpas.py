"""GET /api/mpas and /api/mpas/{mpa_id}."""

from __future__ import annotations

import json

import duckdb
from fastapi import APIRouter, Depends, HTTPException

from iuu_radar.api.deps import get_read_only_connection
from iuu_radar.api.validation import validate_region

router = APIRouter(prefix="/api/mpas", tags=["mpas"])


@router.get("")
def list_mpas(
    region: str,
    conn: duckdb.DuckDBPyConnection = Depends(get_read_only_connection),
) -> list[dict]:
    """List MPAs for a region with risk score, rank, and simplified geometry."""
    validate_region(region)
    rows = conn.execute(
        """
        SELECT mpa_id, region, score,
               rank() OVER (PARTITION BY region ORDER BY score DESC) AS rank
        FROM result_mpa_scores
        WHERE region = ?
        ORDER BY score DESC
        """,
        [region],
    ).fetchall()
    columns = ["mpa_id", "region", "score", "rank"]
    return [dict(zip(columns, row, strict=True)) for row in rows]


@router.get("/{mpa_id}")
def get_mpa(
    mpa_id: str,
    conn: duckdb.DuckDBPyConnection = Depends(get_read_only_connection),
) -> dict:
    """Return one MPA's detail plus its top contributing vessels."""
    mpa_row = conn.execute(
        "SELECT mpa_id, region, score FROM result_mpa_scores WHERE mpa_id = ?", [mpa_id]
    ).fetchone()
    if mpa_row is None:
        raise HTTPException(status_code=404, detail="MPA not found.")

    top_vessels = conn.execute(
        """
        SELECT vessel_id, score, reasons
        FROM result_vessels
        WHERE region = ?
        ORDER BY score DESC
        LIMIT 5
        """,
        [mpa_row[1]],
    ).fetchall()

    return {
        "mpa_id": mpa_row[0],
        "region": mpa_row[1],
        "score": mpa_row[2],
        "top_vessels": [
            {"vessel_id": v[0], "score": v[1], "reasons": json.loads(v[2])} for v in top_vessels
        ],
    }
