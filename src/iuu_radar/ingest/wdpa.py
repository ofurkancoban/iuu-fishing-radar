"""Load Marine Protected Area polygons from the World Database on Protected Areas (WDPA).

WDPA data may not be redistributed. Raw geometry is cached to data/raw/ (gitignored,
VPS-only) and the API must only ever serve simplified display geometry and derived
scores, never the raw WDPA polygons.
"""

from __future__ import annotations

from pathlib import Path

from iuu_radar.config import REPO_ROOT

RAW_DIR = REPO_ROOT / "data" / "raw" / "wdpa"


def load_mpa_polygons(region_cfg: dict) -> Path:
    """Load MPA polygons for the configured region (bbox and/or WDPA ids) into data/raw/wdpa/.

    Source: protectedplanet.net shapefile/geodatabase download, or the Earth Engine
    catalog asset WCMC/WDPA/current/polygons.
    """
    raise NotImplementedError("Implement in Phase 1: download/read WDPA polygons for the region")
