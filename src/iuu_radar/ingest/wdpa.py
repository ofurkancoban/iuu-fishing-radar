"""Load Marine Protected Area polygons from the World Database on Protected Areas (WDPA).

WDPA data may not be redistributed. The source file (shapefile or geodatabase
downloaded from protectedplanet.net) is expected on disk under data/raw/wdpa/source/
and is read locally with GeoPandas; nothing is fetched from a redistribution
endpoint. Raw geometry is cached to data/raw/ (gitignored, VPS-only) and the API
must only ever serve simplified display geometry and derived scores, never the
raw WDPA polygons.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

from iuu_radar.config import REPO_ROOT

RAW_DIR = REPO_ROOT / "data" / "raw" / "wdpa"
SOURCE_DIR = RAW_DIR / "source"


def load_mpa_polygons(region: str, region_cfg: dict) -> Path:
    """Filter the local WDPA source layer to the region bbox and cache it as GeoJSON.

    Expects WDPA polygon shapefile(s) or a geodatabase downloaded manually from
    protectedplanet.net and placed under data/raw/wdpa/source/ (searched
    recursively). The current WDPA/WD-OECM combined bulk export splits the
    global polygon layer across several same-named "*-polygons.shp" files for
    size reasons (e.g. one per data/raw/wdpa/source/part*/) and ships a
    separate "*-points.shp" layer for point-only sites; only the polygon
    layer is used here since the proximity-zone spatial join (inside/edge/
    outside) requires MPA geometry, not points. Every polygon match is read
    and concatenated before filtering. Raises FileNotFoundError with setup
    instructions if no source file is found.
    """
    out_path = RAW_DIR / f"{region}.geojson"
    if out_path.exists():
        return out_path

    source_files = list(SOURCE_DIR.rglob("*polygons.shp")) + list(SOURCE_DIR.rglob("*.gdb"))
    if not source_files:
        # Fall back to any .shp for a plain (non-split, non-WD-OECM-merged) WDPA export.
        source_files = list(SOURCE_DIR.rglob("*.shp"))
    if not source_files:
        raise FileNotFoundError(
            f"No WDPA source layer found under {SOURCE_DIR}. Download the WDPA "
            "shapefile or geodatabase for your region from protectedplanet.net "
            "and place it there before running ingestion."
        )

    min_lon, min_lat, max_lon, max_lat = region_cfg["bbox"]
    parts = [gpd.read_file(f, bbox=(min_lon, min_lat, max_lon, max_lat)) for f in source_files]
    mpas = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=parts[0].crs)

    # Current WDPA/WD-OECM combined exports key sites by SITE_ID (formerly WDPAID).
    site_ids = region_cfg.get("mpa", {}).get("wdpa_ids") or []
    if site_ids:
        mpas = mpas[mpas["SITE_ID"].astype(str).isin([str(i) for i in site_ids])]

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    mpas.to_file(out_path, driver="GeoJSON")
    return out_path


if __name__ == "__main__":
    from iuu_radar.config import load_regions

    for _region, _region_cfg in load_regions().items():
        load_mpa_polygons(_region, _region_cfg)
