"""Unit tests for spatial proximity zone assignment and H3 indexing, using
small synthetic geometry. No network access."""

from __future__ import annotations

import geopandas as gpd
from shapely.geometry import Point, Polygon

from iuu_radar.spatial.indexing import aggregate_hotspots, assign_h3_cell
from iuu_radar.spatial.mpa import assign_proximity_zone, buffer_mpas


def _mpa_gdf() -> gpd.GeoDataFrame:
    square = Polygon([(-91, -1), (-90, -1), (-90, 0), (-91, 0)])
    return gpd.GeoDataFrame({"mpa_id": ["1"], "geometry": [square]}, crs="EPSG:4326")


def test_buffer_mpas_grows_geometry():
    mpas = _mpa_gdf()
    buffered = buffer_mpas(mpas, edge_buffer_km=10)
    assert buffered.iloc[0]["buffered"].area > mpas.iloc[0]["geometry"].area


def test_assign_proximity_zone_inside_edge_outside():
    mpas = _mpa_gdf()
    events = gpd.GeoDataFrame(
        {
            "event_id": ["inside", "edge", "outside"],
            "geometry": [
                Point(-90.5, -0.5),  # inside the square
                Point(-89.98, -0.5),  # just outside the boundary, within 10km buffer
                Point(50, 50),  # far away
            ],
        },
        crs="EPSG:4326",
    )

    result = assign_proximity_zone(events, mpas, edge_buffer_km=10)
    zones = dict(zip(result["event_id"], result["proximity_zone"], strict=True))

    assert zones["inside"] == "inside"
    assert zones["edge"] == "edge"
    assert zones["outside"] == "outside"


def test_assign_h3_cell_and_aggregate():
    events = gpd.GeoDataFrame(
        {
            "region": ["default", "default", "default"],
            "geometry": [Point(-90.5, -0.5), Point(-90.5001, -0.5001), Point(10, 10)],
        },
        crs="EPSG:4326",
    )

    with_h3 = assign_h3_cell(events, resolution=6)
    assert with_h3["h3_cell"].notna().all()

    hotspots = aggregate_hotspots(with_h3)
    assert hotspots["intensity"].sum() == 3
    assert hotspots.iloc[0]["intensity"] >= 1
