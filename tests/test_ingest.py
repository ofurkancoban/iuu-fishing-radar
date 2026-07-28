"""Unit tests for ingestion caching behavior. No network access; the GFW client and
WDPA source layer are mocked / use small synthetic fixtures."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import geopandas as gpd
import pytest
from shapely.geometry import Polygon

from iuu_radar.config import Settings
from iuu_radar.ingest import gfw as gfw_ingest
from iuu_radar.ingest import wdpa as wdpa_ingest

REGION_CFG = {
    "bbox": [-92.5, -1.8, -88.5, 1.8],
    "date_range": {"start": "2024-01-01", "end": "2024-03-31"},
    "mpa": {"wdpa_ids": []},
}


def test_fetch_events_skips_network_when_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(gfw_ingest, "RAW_DIR", tmp_path / "gfw")
    cache_path = gfw_ingest._cache_path("default", "events_gap")
    cache_path.write_text(json.dumps([{"id": "1"}]))

    with patch("gfwapiclient.Client") as mock_client_cls:
        result = asyncio.run(
            gfw_ingest.fetch_events("default", REGION_CFG, Settings(gfw_api_token="x"), "gap")
        )

    assert result == cache_path
    mock_client_cls.assert_not_called()


def test_fetch_events_calls_client_and_caches(tmp_path, monkeypatch):
    monkeypatch.setattr(gfw_ingest, "RAW_DIR", tmp_path / "gfw")

    row = MagicMock()
    row.model_dump.return_value = {"id": "abc"}
    fake_result = MagicMock(data=[row])

    fake_client = MagicMock()
    fake_client.events.get_all_events = AsyncMock(return_value=fake_result)

    with patch("gfwapiclient.Client", return_value=fake_client):
        result = asyncio.run(
            gfw_ingest.fetch_events("default", REGION_CFG, Settings(gfw_api_token="x"), "gap")
        )

    assert result.exists()
    assert json.loads(result.read_text()) == [{"id": "abc"}]
    fake_client.events.get_all_events.assert_awaited_once()


def test_load_mpa_polygons_missing_source_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(wdpa_ingest, "RAW_DIR", tmp_path / "wdpa")
    monkeypatch.setattr(wdpa_ingest, "SOURCE_DIR", tmp_path / "wdpa" / "source")

    with pytest.raises(FileNotFoundError):
        wdpa_ingest.load_mpa_polygons("default", REGION_CFG)


def test_load_mpa_polygons_filters_by_bbox(tmp_path, monkeypatch):
    raw_dir = tmp_path / "wdpa"
    source_dir = raw_dir / "source"
    source_dir.mkdir(parents=True)
    monkeypatch.setattr(wdpa_ingest, "RAW_DIR", raw_dir)
    monkeypatch.setattr(wdpa_ingest, "SOURCE_DIR", source_dir)

    inside = Polygon([(-91, -1), (-90, -1), (-90, 0), (-91, 0)])
    outside = Polygon([(50, 50), (51, 50), (51, 51), (50, 51)])
    gdf = gpd.GeoDataFrame(
        {"WDPAID": [1, 2], "geometry": [inside, outside]}, crs="EPSG:4326"
    )
    gdf.to_file(source_dir / "wdpa.shp")

    out_path = wdpa_ingest.load_mpa_polygons("default", REGION_CFG)
    result = gpd.read_file(out_path)

    assert len(result) == 1
    assert result.iloc[0]["WDPAID"] == 1
