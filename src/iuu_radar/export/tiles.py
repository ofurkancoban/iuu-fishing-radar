"""Build hotspots.pmtiles and mpa.pmtiles via tippecanoe into tiles/."""

from __future__ import annotations

from pathlib import Path

from iuu_radar.config import REPO_ROOT

TILES_DIR = REPO_ROOT / "tiles"


def build_hotspot_tiles(hotspots_geojson: Path) -> Path:
    """Run tippecanoe over the hotspots GeoJSON to produce tiles/hotspots.pmtiles."""
    raise NotImplementedError("Implement in Phase 5")


def build_mpa_tiles(mpa_geojson: Path) -> Path:
    """Simplify MPA display geometry and run tippecanoe to produce tiles/mpa.pmtiles."""
    raise NotImplementedError("Implement in Phase 5")
