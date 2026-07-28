"""GET /api/vessels and /api/vessels/{vessel_id}."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/vessels", tags=["vessels"])


@router.get("")
def list_vessels(
    region: str, min_score: float = 0.0, limit: int = 50, offset: int = 0
) -> list[dict]:
    """List ranked flagged vessels with score and reason strings, paginated and bounded."""
    raise NotImplementedError("Implement in Phase 6")


@router.get("/{vessel_id}")
def get_vessel(vessel_id: str) -> dict:
    """Return one vessel's detail: features, flags, and reason strings."""
    raise NotImplementedError("Implement in Phase 6")
