"""GET /api/anomalies/latest?region=&limit=."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/anomalies", tags=["anomalies"])


@router.get("/latest")
def latest_anomalies(region: str, limit: int = 50) -> list[dict]:
    """Return the most recent flagged anomalies, used to seed the live feed's initial state."""
    raise NotImplementedError("Implement in Phase 6")
