"""Unit tests for loading cached raw GFW/WDPA files into DuckDB raw tables.

Uses an in-memory-style temp DuckDB file and small synthetic fixtures. No
network access.
"""

from __future__ import annotations

import json

import duckdb
import geopandas as gpd
from shapely.geometry import Polygon

from iuu_radar.ingest import duckdb_raw


def test_load_events_and_fishing_effort(tmp_path, monkeypatch):
    gfw_raw = tmp_path / "gfw"
    region_dir = gfw_raw / "default"
    region_dir.mkdir(parents=True)
    (region_dir / "events_gap.json").write_text(
        json.dumps([{"id": "e1", "lat": 0.1, "lon": -90.1}])
    )
    (region_dir / "fishing_effort.json").write_text(
        json.dumps([{"vessel_id": "v1", "hours": 3.5}])
    )
    monkeypatch.setattr(duckdb_raw, "GFW_RAW_DIR", gfw_raw)

    duckdb_path = tmp_path / "test.duckdb"
    duckdb_raw.load_all("default", duckdb_path=duckdb_path)

    conn = duckdb.connect(str(duckdb_path))
    events = conn.execute("SELECT event_type, region FROM raw.raw_events").fetchall()
    effort = conn.execute("SELECT vessel_id, region FROM raw.raw_fishing_effort").fetchall()
    conn.close()

    assert events == [("gap", "default")]
    assert effort == [("v1", "default")]


def test_load_events_rerun_replaces_region(tmp_path, monkeypatch):
    gfw_raw = tmp_path / "gfw"
    region_dir = gfw_raw / "default"
    region_dir.mkdir(parents=True)
    (region_dir / "events_gap.json").write_text(json.dumps([{"id": "e1"}]))
    monkeypatch.setattr(duckdb_raw, "GFW_RAW_DIR", gfw_raw)

    duckdb_path = tmp_path / "test.duckdb"
    duckdb_raw.load_all("default", duckdb_path=duckdb_path)
    duckdb_raw.load_all("default", duckdb_path=duckdb_path)

    conn = duckdb.connect(str(duckdb_path))
    count = conn.execute("SELECT count(*) FROM raw.raw_events").fetchone()[0]
    conn.close()

    assert count == 1


def test_load_mpas(tmp_path, monkeypatch):
    wdpa_raw = tmp_path / "wdpa"
    wdpa_raw.mkdir(parents=True)
    gdf = gpd.GeoDataFrame(
        {"WDPAID": [1], "geometry": [Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])]},
        crs="EPSG:4326",
    )
    gdf.to_file(wdpa_raw / "default.geojson", driver="GeoJSON")
    monkeypatch.setattr(duckdb_raw, "WDPA_RAW_DIR", wdpa_raw)

    duckdb_path = tmp_path / "test.duckdb"
    duckdb_raw.load_all("default", duckdb_path=duckdb_path)

    conn = duckdb.connect(str(duckdb_path))
    conn.execute("INSTALL spatial")
    conn.execute("LOAD spatial")
    count = conn.execute("SELECT count(*) FROM raw.raw_mpas WHERE region = 'default'").fetchone()[0]
    conn.close()

    assert count == 1
