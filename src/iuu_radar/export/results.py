"""Write pipeline outputs into the DuckDB result tables the API reads.

Tables: result_mpa_scores, result_hotspots, result_vessels, result_anomalies
(monotonic id column used as the SSE cursor). The pipeline holds the only
write connection; the API opens DuckDB read-only.
"""

from __future__ import annotations

import duckdb
import pandas as pd


def write_mpa_scores(conn: duckdb.DuckDBPyConnection, mpa_scores: pd.DataFrame) -> None:
    """Write result_mpa_scores: mpa_id, region, score, rank, geometry_simplified."""
    raise NotImplementedError("Implement in Phase 4")


def write_hotspots(conn: duckdb.DuckDBPyConnection, hotspots: pd.DataFrame) -> None:
    """Write result_hotspots: h3_cell, region, intensity."""
    raise NotImplementedError("Implement in Phase 4")


def write_vessels(conn: duckdb.DuckDBPyConnection, vessels: pd.DataFrame) -> None:
    """Write result_vessels: vessel_id, region, score, flags, reasons, last_seen."""
    raise NotImplementedError("Implement in Phase 4")


def write_anomalies(conn: duckdb.DuckDBPyConnection, anomalies: pd.DataFrame) -> pd.DataFrame:
    """Append new rows to result_anomalies with a monotonic id; returns the newly written rows."""
    raise NotImplementedError("Implement in Phase 4")
