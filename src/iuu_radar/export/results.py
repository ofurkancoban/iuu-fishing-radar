"""Write pipeline outputs into the DuckDB result tables the API reads.

Tables: result_mpa_scores, result_hotspots, result_vessels, result_anomalies
(monotonic id column used as the SSE cursor). The pipeline holds the only
write connection; the API opens DuckDB read-only.
"""

from __future__ import annotations

import json

import duckdb
import pandas as pd


def write_mpa_scores(conn: duckdb.DuckDBPyConnection, mpa_scores: pd.DataFrame) -> None:
    """Write result_mpa_scores: mpa_id, region, score, rank, geometry_simplified."""
    conn.execute("CREATE OR REPLACE TABLE result_mpa_scores AS SELECT * FROM mpa_scores")


def write_hotspots(conn: duckdb.DuckDBPyConnection, hotspots: pd.DataFrame) -> None:
    """Write result_hotspots: h3_cell, region, intensity."""
    conn.execute("CREATE OR REPLACE TABLE result_hotspots AS SELECT * FROM hotspots")


def write_vessels(conn: duckdb.DuckDBPyConnection, vessels: pd.DataFrame) -> None:
    """Write result_vessels: vessel_id, region, score, flags, reasons, last_seen.

    flags and reasons are stored as JSON strings since they are variable-length
    lists; the API deserializes them when building responses.
    """
    out = vessels.copy()
    out["flags"] = out["flags"].apply(json.dumps)
    out["reasons"] = out["reasons"].apply(json.dumps)
    conn.execute("CREATE OR REPLACE TABLE result_vessels AS SELECT * FROM out")


def write_anomalies(conn: duckdb.DuckDBPyConnection, anomalies: pd.DataFrame) -> pd.DataFrame:
    """Append new rows to result_anomalies with a monotonic id; returns the newly written rows.

    result_anomalies is append-only: existing ids are never reused, so the SSE
    feed can safely track "rows newer than the last sent id" as its cursor.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS result_anomalies (
            id BIGINT,
            region VARCHAR,
            vessel_id VARCHAR,
            lon DOUBLE,
            lat DOUBLE,
            ts TIMESTAMP,
            reasons VARCHAR
        )
        """
    )
    if anomalies.empty:
        return anomalies.assign(id=pd.Series(dtype="int64"))

    next_id = conn.execute("SELECT coalesce(max(id), 0) + 1 FROM result_anomalies").fetchone()[0]

    out = anomalies.copy()
    out["reasons"] = out["reasons"].apply(json.dumps)
    out.insert(0, "id", range(next_id, next_id + len(out)))

    conn.execute("INSERT INTO result_anomalies SELECT * FROM out")
    return out
