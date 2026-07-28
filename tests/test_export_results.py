"""Unit tests for writing pipeline outputs into DuckDB result tables."""

from __future__ import annotations

import json

import duckdb
import pandas as pd

from iuu_radar.export.results import (
    write_anomalies,
    write_hotspots,
    write_mpa_scores,
    write_vessels,
)


def test_write_mpa_scores_and_hotspots():
    conn = duckdb.connect(":memory:")
    write_mpa_scores(
        conn, "default", pd.DataFrame([{"mpa_id": "1", "region": "default", "score": 80.0}])
    )
    write_hotspots(
        conn,
        "default",
        pd.DataFrame([{"h3_cell": "abc", "region": "default", "intensity": 3}]),
    )

    assert conn.execute("SELECT count(*) FROM result_mpa_scores").fetchone()[0] == 1
    assert conn.execute("SELECT count(*) FROM result_hotspots").fetchone()[0] == 1
    conn.close()


def test_write_vessels_preserves_other_regions():
    conn = duckdb.connect(":memory:")
    write_vessels(
        conn,
        "default",
        pd.DataFrame(
            [{"vessel_id": "v1", "region": "default", "score": 50.0,
              "flags": [], "reasons": [], "last_seen": None}]
        ),
    )
    write_vessels(
        conn,
        "turkey_seas",
        pd.DataFrame(
            [{"vessel_id": "v2", "region": "turkey_seas", "score": 60.0,
              "flags": [], "reasons": [], "last_seen": None}]
        ),
    )

    regions = conn.execute("SELECT region FROM result_vessels ORDER BY region").fetchall()
    assert regions == [("default",), ("turkey_seas",)]
    conn.close()


def test_write_vessels_serializes_flags_and_reasons():
    conn = duckdb.connect(":memory:")
    vessels = pd.DataFrame(
        [{"vessel_id": "v1", "region": "default", "score": 90.0,
          "flags": ["gap_near_mpa"], "reasons": ["1 gap event near MPA."],
          "last_seen": "2024-01-01"}]
    )
    write_vessels(conn, "default", vessels)

    row = conn.execute("SELECT flags, reasons FROM result_vessels").fetchone()
    assert json.loads(row[0]) == ["gap_near_mpa"]
    assert json.loads(row[1]) == ["1 gap event near MPA."]
    conn.close()


def test_write_anomalies_appends_with_monotonic_id():
    conn = duckdb.connect(":memory:")
    first_batch = pd.DataFrame(
        [{"region": "default", "vessel_id": "v1", "lon": -90.5, "lat": -0.5,
          "ts": pd.Timestamp("2024-01-05"), "reasons": ["gap near mpa"]}]
    )
    written_first = write_anomalies(conn, first_batch)
    assert list(written_first["id"]) == [1]

    second_batch = pd.DataFrame(
        [{"region": "default", "vessel_id": "v2", "lon": -90.1, "lat": -0.1,
          "ts": pd.Timestamp("2024-01-06"), "reasons": ["dark then reappear"]}]
    )
    written_second = write_anomalies(conn, second_batch)
    assert list(written_second["id"]) == [2]

    total = conn.execute("SELECT count(*) FROM result_anomalies").fetchone()[0]
    assert total == 2
    conn.close()
