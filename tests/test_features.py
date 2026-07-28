"""Unit tests for feature construction, against an in-memory DuckDB seeded with
synthetic mart tables (no dbt run, no network)."""

from __future__ import annotations

import duckdb
import pandas as pd
import pytest

from iuu_radar.features.build import build_cell_features, build_vessel_features


@pytest.fixture
def conn():
    connection = duckdb.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE mart_vessel_effort AS SELECT * FROM (VALUES
            ('default', 'v1', 5.0, 1, 0, 0, 1, 0, 0),
            ('default', 'v2', 1.0, 0, 0, 1, 0, 0, 0)
        ) AS t(region, vessel_id, total_fishing_hours, events_inside, events_edge,
               events_outside, gap_event_count, encounter_count_inside,
               loitering_count_inside)
        """
    )
    connection.execute(
        """
        CREATE TABLE mart_events_mpa AS SELECT * FROM (VALUES
            ('e1', 'default', 'gap', TIMESTAMP '2024-01-05 00:00:00',
             TIMESTAMP '2024-01-06 00:00:00', -0.5, -90.5, 'v1', '1', 'inside'),
            ('e2', 'default', 'fishing', TIMESTAMP '2024-01-07 00:00:00',
             TIMESTAMP '2024-01-07 02:00:00', -0.5, -90.5, 'v1', '1', 'inside'),
            ('e3', 'default', 'fishing', TIMESTAMP '2024-01-10 00:00:00',
             TIMESTAMP '2024-01-10 02:00:00', 10.0, 10.0, 'v2', NULL, 'outside')
        ) AS t(event_id, region, event_type, start_ts, end_ts, lat, lon,
               vessel_id, mpa_id, proximity_zone)
        """
    )
    yield connection
    connection.close()


def test_build_vessel_features_gap_near_mpa(conn):
    features = build_vessel_features(conn, "default")
    v1 = features[features["vessel_id"] == "v1"].iloc[0]
    v2 = features[features["vessel_id"] == "v2"].iloc[0]

    assert v1["total_fishing_hours"] == 5.0
    assert v1["dark_then_reappear_count"] == 1
    assert v2["dark_then_reappear_count"] == 0


def test_build_cell_features_aggregates_by_h3(conn):
    cells = build_cell_features(conn, "default", resolution=6)
    assert isinstance(cells, pd.DataFrame)
    assert cells["intensity"].sum() == 3
