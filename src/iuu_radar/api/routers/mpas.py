"""GET /api/mpas and /api/mpas/{mpa_id}."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/mpas", tags=["mpas"])


@router.get("")
def list_mpas(region: str) -> list[dict]:
    """List MPAs for a region with risk score, rank, and simplified geometry."""
    raise NotImplementedError("Implement in Phase 6")


@router.get("/{mpa_id}")
def get_mpa(mpa_id: str) -> dict:
    """Return one MPA's detail plus its top contributing vessels."""
    raise NotImplementedError("Implement in Phase 6")
