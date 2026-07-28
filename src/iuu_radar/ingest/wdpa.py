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

from iuu_radar.config import REPO_ROOT

RAW_DIR = REPO_ROOT / "data" / "raw" / "wdpa"
SOURCE_DIR = RAW_DIR / "source"


def load_mpa_polygons(region: str, region_cfg: dict) -> Path:
    """Filter the local WDPA source layer to the region bbox and cache it as GeoJSON.

    Expects a WDPA shapefile or geodatabase downloaded manually from
    protectedplanet.net and placed under data/raw/wdpa/source/ (any .shp or
    .gdb file). Raises FileNotFoundError with setup instructions if missing.
    """
    out_path = RAW_DIR / f"{region}.geojson"
    if out_path.exists():
        return out_path

    source_files = list(SOURCE_DIR.glob("*.shp")) + list(SOURCE_DIR.glob("*.gdb"))
    if not source_files:
        raise FileNotFoundError(
            f"No WDPA source layer found under {SOURCE_DIR}. Download the WDPA "
            "shapefile or geodatabase for your region from protectedplanet.net "
            "and place it there before running ingestion."
        )

    mpas = gpd.read_file(source_files[0])
    wdpa_ids = region_cfg.get("mpa", {}).get("wdpa_ids") or []
    if wdpa_ids:
        mpas = mpas[mpas["WDPAID"].astype(str).isin([str(i) for i in wdpa_ids])]
    else:
        min_lon, min_lat, max_lon, max_lat = region_cfg["bbox"]
        mpas = mpas.cx[min_lon:max_lon, min_lat:max_lat]

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    mpas.to_file(out_path, driver="GeoJSON")
    return out_path


if __name__ == "__main__":
    from iuu_radar.config import load_regions

    for _region, _region_cfg in load_regions().items():
        load_mpa_polygons(_region, _region_cfg)
