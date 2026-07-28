"""Unit tests for tile export. tippecanoe is mocked; no system binary or network
access required."""

from __future__ import annotations

import json
from unittest.mock import patch

import pandas as pd

from iuu_radar.export.tiles import build_hotspot_tiles, build_mpa_tiles, hotspots_to_geojson


def test_hotspots_to_geojson_writes_h3_boundaries(tmp_path):
    hotspots = pd.DataFrame(
        [{"region": "default", "h3_cell": "862830827ffffff", "intensity": 5}]
    )
    out_path = tmp_path / "hotspots.geojson"

    result = hotspots_to_geojson(hotspots, out_path)
    data = json.loads(result.read_text())

    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 1
    assert data["features"][0]["properties"]["intensity"] == 5
    assert data["features"][0]["geometry"]["type"] == "Polygon"


def test_build_hotspot_tiles_invokes_tippecanoe(tmp_path):
    geojson_path = tmp_path / "hotspots.geojson"
    geojson_path.write_text(json.dumps({"type": "FeatureCollection", "features": []}))
    out_path = tmp_path / "hotspots.pmtiles"

    with patch("iuu_radar.export.tiles.subprocess.run") as mock_run:
        result = build_hotspot_tiles(geojson_path, out_path)

    assert result == out_path
    args = mock_run.call_args.args[0]
    assert args[0] == "tippecanoe"
    assert str(geojson_path) in args


def test_build_mpa_tiles_invokes_tippecanoe(tmp_path):
    geojson_path = tmp_path / "mpa.geojson"
    geojson_path.write_text(json.dumps({"type": "FeatureCollection", "features": []}))
    out_path = tmp_path / "mpa.pmtiles"

    with patch("iuu_radar.export.tiles.subprocess.run") as mock_run:
        result = build_mpa_tiles(geojson_path, out_path)

    assert result == out_path
    args = mock_run.call_args.args[0]
    assert "--simplification" in args
