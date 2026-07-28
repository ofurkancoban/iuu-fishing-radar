"""MPA polygon loading, buffering, and proximity zone assignment (inside / edge / outside)."""

from __future__ import annotations

import geopandas as gpd


def buffer_mpas(mpas: gpd.GeoDataFrame, edge_buffer_km: float) -> gpd.GeoDataFrame:
    """Return MPA polygons with an added edge-buffer geometry column, in a projected CRS."""
    raise NotImplementedError("Implement in Phase 3")


def assign_proximity_zone(
    events: gpd.GeoDataFrame, mpas: gpd.GeoDataFrame, edge_buffer_km: float
) -> gpd.GeoDataFrame:
    """Tag each event with 'inside', 'edge', or 'outside' relative to the nearest MPA.

    Prefer DuckDB spatial (ST_Contains / ST_DWithin) for this join where the caller
    already holds a DuckDB connection; this GeoPandas path is the fallback for
    operations DuckDB cannot do cleanly.
    """
    raise NotImplementedError("Implement in Phase 3")
