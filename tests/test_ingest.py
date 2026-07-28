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
    fake_result = MagicMock()
    fake_result.data.return_value = [row]

    fake_client = MagicMock()
    fake_client.events.get_all_events = AsyncMock(return_value=fake_result)

    with patch("gfwapiclient.Client", return_value=fake_client):
        result = asyncio.run(
            gfw_ingest.fetch_events("default", REGION_CFG, Settings(gfw_api_token="x"), "gap")
        )

    assert result.exists()
    assert json.loads(result.read_text()) == [{"id": "abc"}]
    fake_client.events.get_all_events.assert_awaited_once()


def test_fetch_events_paginates_without_holding_full_result_in_memory(tmp_path, monkeypatch):
    monkeypatch.setattr(gfw_ingest, "RAW_DIR", tmp_path / "gfw")
    monkeypatch.setattr(gfw_ingest, "EVENTS_PAGE_SIZE", 2)

    def make_row(row_id: str) -> MagicMock:
        row = MagicMock()
        row.model_dump.return_value = {"id": row_id}
        return row

    # Three pages of 2, 2, then 1 row (last page shorter than page size ends pagination).
    pages = [
        MagicMock(data=MagicMock(return_value=[make_row("1"), make_row("2")])),
        MagicMock(data=MagicMock(return_value=[make_row("3"), make_row("4")])),
        MagicMock(data=MagicMock(return_value=[make_row("5")])),
    ]
    fake_client = MagicMock()
    fake_client.events.get_all_events = AsyncMock(side_effect=pages)

    with patch("gfwapiclient.Client", return_value=fake_client):
        result = asyncio.run(
            gfw_ingest.fetch_events("default", REGION_CFG, Settings(gfw_api_token="x"), "gap")
        )

    assert json.loads(result.read_text()) == [
        {"id": "1"}, {"id": "2"}, {"id": "3"}, {"id": "4"}, {"id": "5"}
    ]
    assert fake_client.events.get_all_events.await_count == 3
    calls = fake_client.events.get_all_events.await_args_list
    assert [c.kwargs["offset"] for c in calls] == [0, 2, 4]


def test_month_starts_splits_multi_month_range():
    assert gfw_ingest._month_starts("2024-01-01", "2024-03-31") == [
        ("2024-01-01", "2024-01-31"),
        ("2024-02-01", "2024-02-29"),
        ("2024-03-01", "2024-03-31"),
    ]


def test_month_starts_single_month_partial_range():
    assert gfw_ingest._month_starts("2024-01-15", "2024-01-20") == [
        ("2024-01-15", "2024-01-20")
    ]


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
        {"SITE_ID": [1, 2], "geometry": [inside, outside]}, crs="EPSG:4326"
    )
    gdf.to_file(source_dir / "wdpa.shp")

    out_path = wdpa_ingest.load_mpa_polygons("default", REGION_CFG)
    result = gpd.read_file(out_path)

    assert len(result) == 1
    assert result.iloc[0]["SITE_ID"] == 1
