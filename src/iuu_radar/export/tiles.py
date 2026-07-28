"""Build hotspots.pmtiles and mpa.pmtiles via tippecanoe into tiles/.

tippecanoe is not a Python dependency; it is installed as a system binary
(apt/brew on the host, or baked into the pipeline container image in Phase 8)
and invoked here as a subprocess. Geometry is simplified before tiling so the
frontend receives small payloads per section 5 (payload discipline) of
CLAUDE.md.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pandas as pd

from iuu_radar.config import REPO_ROOT

TILES_DIR = REPO_ROOT / "tiles"

# tippecanoe --simplification factor for MPA display geometry (higher = coarser).
MPA_SIMPLIFY_FACTOR = 10


def _run_tippecanoe(args: list[str]) -> None:
    """Run tippecanoe with the given arguments, raising on a non-zero exit code."""
    subprocess.run(["tippecanoe", *args], check=True, capture_output=True, text=True)


def hotspots_to_geojson(hotspots: pd.DataFrame, out_path: Path) -> Path:
    """Write per-H3-cell hotspot intensity to a GeoJSON FeatureCollection.

    Each feature's geometry is the H3 cell boundary polygon; h3 is imported
    lazily here to keep this module's import cost low for callers that only
    need the tiling step.
    """
    import h3

    features = []
    for _, row in hotspots.iterrows():
        boundary = h3.cell_to_boundary(row["h3_cell"])
        ring = [[lon, lat] for lat, lon in boundary]
        ring.append(ring[0])
        features.append(
            {
                "type": "Feature",
                "properties": {"region": row["region"], "intensity": int(row["intensity"])},
                "geometry": {"type": "Polygon", "coordinates": [ring]},
            }
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    return out_path


def build_hotspot_tiles(
    hotspots_geojson: Path, out_path: Path = TILES_DIR / "hotspots.pmtiles"
) -> Path:
    """Run tippecanoe over the hotspots GeoJSON to produce tiles/hotspots.pmtiles."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _run_tippecanoe(
        [
            "-o",
            str(out_path),
            "-l",
            "hotspots",
            "-zg",
            "--drop-densest-as-needed",
            "--force",
            str(hotspots_geojson),
        ]
    )
    return out_path


def build_mpa_tiles(mpa_geojson: Path, out_path: Path = TILES_DIR / "mpa.pmtiles") -> Path:
    """Simplify MPA display geometry and run tippecanoe to produce tiles/mpa.pmtiles.

    WDPA geometry may not be redistributed in raw form: this always writes to
    the gitignored tiles/ directory served only from the VPS, and tippecanoe's
    simplification keeps the served geometry coarse rather than survey-grade.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _run_tippecanoe(
        [
            "-o",
            str(out_path),
            "-l",
            "mpa",
            "-zg",
            "--simplification",
            str(MPA_SIMPLIFY_FACTOR),
            "--force",
            str(mpa_geojson),
        ]
    )
    return out_path
