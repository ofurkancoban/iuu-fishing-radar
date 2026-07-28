"""GET /api/vessels and /api/vessels/{vessel_id}."""

from __future__ import annotations

import json

import duckdb
from fastapi import APIRouter, Depends, HTTPException

from iuu_radar.api.deps import get_read_only_connection
from iuu_radar.api.validation import validate_limit, validate_offset, validate_region

router = APIRouter(prefix="/api/vessels", tags=["vessels"])


@router.get("")
def list_vessels(
    region: str,
    min_score: float = 0.0,
    limit: int = 50,
    offset: int = 0,
    conn: duckdb.DuckDBPyConnection = Depends(get_read_only_connection),
) -> list[dict]:
    """List ranked flagged vessels with score and reason strings, paginated and bounded."""
    validate_region(region)
    validate_limit(limit)
    validate_offset(offset)

    rows = conn.execute(
        """
        SELECT vessel_id, region, score, flags, reasons, last_seen
        FROM result_vessels
        WHERE region = ? AND score >= ?
        ORDER BY score DESC
        LIMIT ? OFFSET ?
        """,
        [region, min_score, limit, offset],
    ).fetchall()

    return [
        {
            "vessel_id": r[0],
            "region": r[1],
            "score": r[2],
            "flags": json.loads(r[3]),
            "reasons": json.loads(r[4]),
            "last_seen": r[5],
        }
        for r in rows
    ]


@router.get("/{vessel_id}")
def get_vessel(
    vessel_id: str,
    conn: duckdb.DuckDBPyConnection = Depends(get_read_only_connection),
) -> dict:
    """Return one vessel's detail: features, flags, and reason strings."""
    row = conn.execute(
        "SELECT vessel_id, region, score, flags, reasons, last_seen FROM result_vessels "
        "WHERE vessel_id = ?",
        [vessel_id],
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Vessel not found.")

    return {
        "vessel_id": row[0],
        "region": row[1],
        "score": row[2],
        "flags": json.loads(row[3]),
        "reasons": json.loads(row[4]),
        "last_seen": row[5],
    }
