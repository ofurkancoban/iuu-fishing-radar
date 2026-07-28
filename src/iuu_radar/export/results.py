"""Write pipeline outputs into the DuckDB result tables the API reads.

Tables: result_mpa_scores, result_hotspots, result_vessels, result_anomalies
(monotonic id column used as the SSE cursor). The pipeline holds the only
write connection; the API opens DuckDB read-only.
"""

from __future__ import annotations

import json

import duckdb
import pandas as pd


def _replace_region(
    conn: duckdb.DuckDBPyConnection, table: str, region: str, df: pd.DataFrame
) -> None:
    """Create `table` if missing, then replace only `region`'s rows with `df`.

    The pipeline runs one region at a time, so a plain CREATE OR REPLACE would
    wipe out every other region's rows on the next region's run. This keeps
    other regions' results intact.
    """
    conn.execute(f"CREATE TABLE IF NOT EXISTS {table} AS SELECT * FROM df LIMIT 0")
    conn.execute(f"DELETE FROM {table} WHERE region = ?", [region])
    conn.execute(f"INSERT INTO {table} SELECT * FROM df")


def write_mpa_scores(
    conn: duckdb.DuckDBPyConnection, region: str, mpa_scores: pd.DataFrame
) -> None:
    """Write result_mpa_scores: mpa_id, region, score, rank, geometry_simplified."""
    _replace_region(conn, "result_mpa_scores", region, mpa_scores)


def write_hotspots(conn: duckdb.DuckDBPyConnection, region: str, hotspots: pd.DataFrame) -> None:
    """Write result_hotspots: h3_cell, region, intensity."""
    _replace_region(conn, "result_hotspots", region, hotspots)


def write_vessels(conn: duckdb.DuckDBPyConnection, region: str, vessels: pd.DataFrame) -> None:
    """Write result_vessels: vessel_id, region, score, flags, reasons, last_seen.

    flags and reasons are stored as JSON strings since they are variable-length
    lists; the API deserializes them when building responses.
    """
    out = vessels.copy()
    out["flags"] = out["flags"].apply(json.dumps)
    out["reasons"] = out["reasons"].apply(json.dumps)
    _replace_region(conn, "result_vessels", region, out)


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


def write_pipeline_run(
    conn: duckdb.DuckDBPyConnection,
    region: str,
    rows_processed: int,
    anomalies_count: int,
    duration_seconds: float,
    failed: bool,
) -> None:
    """Append one row summarizing a pipeline run, read by metrics.refresh_pipeline_gauges.

    pipeline_runs is append-only history; the API only ever reads the latest
    row per region when refreshing Prometheus gauges on /metrics scrape.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            region VARCHAR,
            rows_processed BIGINT,
            anomalies_count BIGINT,
            duration_seconds DOUBLE,
            failed BOOLEAN,
            ts TIMESTAMP
        )
        """
    )
    conn.execute(
        "INSERT INTO pipeline_runs VALUES (?, ?, ?, ?, ?, now())",
        [region, rows_processed, anomalies_count, duration_seconds, failed],
    )
