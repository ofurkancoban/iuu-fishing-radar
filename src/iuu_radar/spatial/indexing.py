"""H3 cell assignment and aggregation for hotspot generation."""

from __future__ import annotations

import geopandas as gpd
import pandas as pd


def assign_h3_cell(events: gpd.GeoDataFrame, resolution: int) -> gpd.GeoDataFrame:
    """Add an h3_cell column computed at the given resolution from each event's point geometry."""
    raise NotImplementedError("Implement in Phase 3")


def aggregate_hotspots(events_with_h3: gpd.GeoDataFrame) -> pd.DataFrame:
    """Aggregate events per h3_cell into an intensity score for the hotspots result table."""
    raise NotImplementedError("Implement in Phase 3")
