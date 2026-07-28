"""Build per-vessel and per-H3-cell feature matrices from the dbt mart tables.

Reads mart_events_mpa and mart_vessel_effort (built by dbt in the pipeline's
DuckDB file) and adds features that need row-by-row event ordering rather than
a single SQL aggregation, most importantly the "dark then reappear" signal.
"""

from __future__ import annotations

import duckdb
import h3
import pandas as pd

from iuu_radar.spatial.indexing import aggregate_hotspots


def _dark_then_reappear_counts(conn: duckdb.DuckDBPyConnection, region: str) -> pd.DataFrame:
    """Count, per vessel, gap events that start near an MPA and are followed by a
    fishing/loitering event near the same MPA (the vessel went dark, then reappeared
    close to where it disappeared).
    """
    events = conn.execute(
        """
        SELECT vessel_id, mpa_id, event_type, proximity_zone, start_ts, end_ts
        FROM mart_events_mpa
        WHERE region = ? AND vessel_id IS NOT NULL AND mpa_id IS NOT NULL
        ORDER BY vessel_id, start_ts
        """,
        [region],
    ).fetch_df()

    if events.empty:
        return pd.DataFrame(columns=["vessel_id", "dark_then_reappear_count"])

    counts: dict[str, int] = {}
    for vessel_id, group in events.groupby("vessel_id"):
        group = group.reset_index(drop=True)
        gaps = group[
            (group["event_type"] == "gap") & (group["proximity_zone"].isin(["inside", "edge"]))
        ]
        for _, gap in gaps.iterrows():
            reappear = group[
                (group["mpa_id"] == gap["mpa_id"])
                & (group["proximity_zone"].isin(["inside", "edge"]))
                & (group["start_ts"] >= gap["end_ts"])
                & (group["event_type"] != "gap")
            ]
            if not reappear.empty:
                counts[vessel_id] = counts.get(vessel_id, 0) + 1

    return pd.DataFrame(
        {"vessel_id": list(counts.keys()), "dark_then_reappear_count": list(counts.values())}
    )


def build_vessel_features(conn: duckdb.DuckDBPyConnection, region: str) -> pd.DataFrame:
    """Build the per-vessel feature matrix from the dbt mart tables for one region.

    Output columns: vessel_id, total_fishing_hours, events_inside, events_edge,
    events_outside, gap_event_count, encounter_count_inside, loitering_count_inside,
    dark_then_reappear_count.
    """
    base = conn.execute(
        "SELECT * FROM mart_vessel_effort WHERE region = ?", [region]
    ).fetch_df()
    dark_reappear = _dark_then_reappear_counts(conn, region)

    features = base.merge(dark_reappear, on="vessel_id", how="left")
    features["dark_then_reappear_count"] = features["dark_then_reappear_count"].fillna(0).astype(
        int
    )
    return features


def build_cell_features(
    conn: duckdb.DuckDBPyConnection, region: str, resolution: int
) -> pd.DataFrame:
    """Build the per-H3-cell feature matrix (intensity per cell) for one region.

    DuckDB SQL has no native H3 support, so the h3_cell assignment happens here
    in Python (via the h3 library) rather than in the dbt marts.
    """
    events = conn.execute(
        "SELECT region, lat, lon FROM mart_events_mpa WHERE region = ?", [region]
    ).fetch_df()
    if events.empty:
        return pd.DataFrame(columns=["region", "h3_cell", "intensity"])

    events["h3_cell"] = [
        h3.latlng_to_cell(lat, lon, resolution)
        for lat, lon in zip(events["lat"], events["lon"], strict=True)
    ]
    return aggregate_hotspots(events)
