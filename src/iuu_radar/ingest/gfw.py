"""Pull AIS fishing effort and events from the Global Fishing Watch APIs, cached to data/raw/.

Uses the official gfwapiclient (package name gfw-api-python-client). Every fetch
function is cached to disk: a rerun with an existing cache file skips the network
call entirely, so pipeline runs are deterministic and do not re-hit rate limits.
"""

from __future__ import annotations

import json
from pathlib import Path

import gfwapiclient as gfw

from iuu_radar.config import REPO_ROOT, Settings

RAW_DIR = REPO_ROOT / "data" / "raw" / "gfw"

# GFW dataset id for the primary Events API pull, one per event type in region config.
EVENT_DATASET_BY_TYPE = {
    "fishing": "public-global-fishing-events:latest",
    "encounter": "public-global-encounters-events:latest",
    "loitering": "public-global-loitering-events:latest",
    "port_visit": "public-global-port-visits-events:latest",
    "gap": "public-global-gaps-events:latest",
}


def _cache_path(region: str, name: str) -> Path:
    """Build the on-disk cache path for a given region and dataset/event type name."""
    out_dir = RAW_DIR / region
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{name}.json"


def _region_bbox_geojson(bbox: list[float]) -> dict:
    """Build a GeoJSON polygon geometry from a [min_lon, min_lat, max_lon, max_lat] bbox."""
    min_lon, min_lat, max_lon, max_lat = bbox
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [min_lon, min_lat],
                [max_lon, min_lat],
                [max_lon, max_lat],
                [min_lon, max_lat],
                [min_lon, min_lat],
            ]
        ],
    }


def _get_client(settings: Settings) -> gfw.Client:
    """Build a GFW API client from the configured access token."""
    return gfw.Client(access_token=settings.gfw_api_token)


async def fetch_fishing_effort(region: str, region_cfg: dict, settings: Settings) -> Path:
    """Fetch 4Wings apparent fishing effort for a region and cache the raw response.

    Skips the network call if a cache file already exists for this region.
    """
    cache_path = _cache_path(region, "fishing_effort")
    if cache_path.exists():
        return cache_path

    client = _get_client(settings)
    result = await client.fourwings.create_fishing_effort_report(
        spatial_resolution="LOW",
        temporal_resolution="MONTHLY",
        group_by="VESSEL_ID",
        start_date=region_cfg["date_range"]["start"],
        end_date=region_cfg["date_range"]["end"],
        geojson=_region_bbox_geojson(region_cfg["bbox"]),
    )
    cache_path.write_text(json.dumps([row.model_dump(mode="json") for row in result.data()]))
    return cache_path


async def fetch_events(region: str, region_cfg: dict, settings: Settings, event_type: str) -> Path:
    """Fetch Events API results (fishing, encounter, loitering, port_visit, gap) for a region."""
    cache_path = _cache_path(region, f"events_{event_type}")
    if cache_path.exists():
        return cache_path

    dataset = EVENT_DATASET_BY_TYPE[event_type]
    client = _get_client(settings)
    result = await client.events.get_all_events(
        datasets=[dataset],
        start_date=region_cfg["date_range"]["start"],
        end_date=region_cfg["date_range"]["end"],
        geometry=_region_bbox_geojson(region_cfg["bbox"]),
    )
    cache_path.write_text(json.dumps([row.model_dump(mode="json") for row in result.data()]))
    return cache_path


async def fetch_vessel_info(vessel_ids: list[str], settings: Settings) -> Path:
    """Fetch vessel identity/registry info from the Vessels API for a set of vessel ids."""
    cache_path = RAW_DIR / "vessels" / f"{'_'.join(sorted(vessel_ids))[:200]}.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.exists():
        return cache_path

    client = _get_client(settings)
    result = await client.vessels.get_vessels_by_ids(
        ids=vessel_ids, datasets=["public-global-vessel-identity:latest"]
    )
    cache_path.write_text(json.dumps([row.model_dump(mode="json") for row in result.data()]))
    return cache_path


def load_cached(path: Path) -> list[dict]:
    """Load a previously cached raw JSON response from disk."""
    with open(path) as f:
        return json.load(f)


async def _ingest_all_regions() -> None:
    """Ingest fishing effort and every configured event type for every region."""
    import iuu_radar.config as cfg

    settings = Settings()
    regions = cfg.load_regions()
    for region, region_cfg in regions.items():
        await fetch_fishing_effort(region, region_cfg, settings)
        for event_type in region_cfg["gfw"]["event_types"]:
            await fetch_events(region, region_cfg, settings, event_type)


if __name__ == "__main__":
    import asyncio

    asyncio.run(_ingest_all_regions())
