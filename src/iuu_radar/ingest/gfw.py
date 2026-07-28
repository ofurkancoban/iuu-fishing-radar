"""Pull AIS fishing effort and events from the Global Fishing Watch APIs, cached to data/raw/."""

from __future__ import annotations

import json
from pathlib import Path

from iuu_radar.config import REPO_ROOT, Settings

RAW_DIR = REPO_ROOT / "data" / "raw" / "gfw"


def _cache_path(region: str, dataset: str) -> Path:
    """Build the on-disk cache path for a given region and dataset/event type."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    return RAW_DIR / region / f"{dataset}.json"


def fetch_fishing_effort(region: str, region_cfg: dict, settings: Settings) -> Path:
    """Fetch 4Wings apparent fishing effort for a region and cache the raw response.

    Returns the path to the cached JSON. Skips the network call if a cache file
    already exists, so reruns are deterministic and do not re-hit rate limits.
    """
    raise NotImplementedError("Implement in Phase 1 using gfw-api-python-client")


def fetch_events(region: str, region_cfg: dict, settings: Settings, event_type: str) -> Path:
    """Fetch Events API results (fishing, encounter, loitering, port_visit, gap) for a region."""
    raise NotImplementedError("Implement in Phase 1 using gfw-api-python-client")


def fetch_vessel_info(vessel_ids: list[str], settings: Settings) -> Path:
    """Fetch vessel identity/registry info from the Vessels API for a set of vessel ids."""
    raise NotImplementedError("Implement in Phase 1 using gfw-api-python-client")


def load_cached(path: Path) -> dict:
    """Load a previously cached raw JSON response from disk."""
    with open(path) as f:
        return json.load(f)
