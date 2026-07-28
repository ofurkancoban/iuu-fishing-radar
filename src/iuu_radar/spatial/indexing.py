"""H3 cell assignment and aggregation for hotspot generation."""

from __future__ import annotations

import geopandas as gpd
import h3
import pandas as pd


def assign_h3_cell(events: gpd.GeoDataFrame, resolution: int) -> gpd.GeoDataFrame:
    """Add an h3_cell column computed at the given resolution from each event's point geometry."""
    out = events.copy()
    out["h3_cell"] = [
        h3.latlng_to_cell(geom.y, geom.x, resolution) for geom in out.geometry
    ]
    return out


def aggregate_hotspots(events_with_h3: pd.DataFrame) -> pd.DataFrame:
    """Aggregate events per h3_cell into an intensity score for the hotspots result table."""
    return (
        events_with_h3.groupby(["region", "h3_cell"])
        .size()
        .reset_index(name="intensity")
        .sort_values("intensity", ascending=False)
        .reset_index(drop=True)
    )
