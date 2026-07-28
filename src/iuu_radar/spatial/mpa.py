"""MPA polygon buffering and proximity zone assignment (inside / edge / outside).

The primary join path is the DuckDB spatial SQL in dbt/iuu_radar/models/marts/
mart_events_mpa.sql. This GeoPandas path is the fallback for callers that
already hold events/MPAs as GeoDataFrames in memory (for example within
features/build.py) rather than as DuckDB tables.
"""

from __future__ import annotations

import geopandas as gpd

METRIC_CRS = "EPSG:3857"


def buffer_mpas(mpas: gpd.GeoDataFrame, edge_buffer_km: float) -> gpd.GeoDataFrame:
    """Return MPA polygons with an added 'buffered' geometry column, in EPSG:4326.

    Buffering is done in a projected (metric) CRS so edge_buffer_km is accurate,
    then reprojected back to WGS84 to match the input events' CRS.
    """
    projected = mpas.to_crs(METRIC_CRS)
    buffered = projected.buffer(edge_buffer_km * 1000)
    out = mpas.copy()
    out["buffered"] = gpd.GeoSeries(buffered, crs=METRIC_CRS).to_crs(mpas.crs).values
    return out


def assign_proximity_zone(
    events: gpd.GeoDataFrame, mpas: gpd.GeoDataFrame, edge_buffer_km: float
) -> gpd.GeoDataFrame:
    """Tag each event with 'inside', 'edge', or 'outside' relative to the nearest MPA."""
    buffered_mpas = buffer_mpas(mpas, edge_buffer_km)

    inside_idx = set(
        gpd.sjoin(events, mpas[["geometry"]], how="inner", predicate="within").index
    )

    edge_gdf = buffered_mpas.set_geometry("buffered")[["buffered"]].rename_geometry("geometry")
    edge_idx = set(gpd.sjoin(events, edge_gdf, how="inner", predicate="within").index)

    out = events.copy()
    out["proximity_zone"] = "outside"
    out.loc[out.index.isin(edge_idx), "proximity_zone"] = "edge"
    out.loc[out.index.isin(inside_idx), "proximity_zone"] = "inside"
    return out
