"""Load cached raw GFW and WDPA responses into DuckDB raw tables.

Reads the JSON/GeoJSON files written by ingest/gfw.py and ingest/wdpa.py from
data/raw/ and loads them, largely untyped, into raw_* tables in the pipeline's
DuckDB file. dbt staging models (Phase 2) clean and type these into stg_* views.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import duckdb

from iuu_radar.config import REPO_ROOT
from iuu_radar.ingest.gfw import EVENT_DATASET_BY_TYPE
from iuu_radar.ingest.gfw import RAW_DIR as GFW_RAW_DIR
from iuu_radar.ingest.wdpa import RAW_DIR as WDPA_RAW_DIR

DUCKDB_PATH = REPO_ROOT / "data" / "processed" / "iuu_radar.duckdb"


def load_events(conn: duckdb.DuckDBPyConnection, region: str) -> None:
    """Load cached events_<type>.json files for a region into raw_events."""
    conn.execute("CREATE SCHEMA IF NOT EXISTS raw")
    rows: list[dict] = []
    for event_type in EVENT_DATASET_BY_TYPE:
        path = GFW_RAW_DIR / region / f"events_{event_type}.json"
        if not path.exists():
            continue
        for row in json.loads(path.read_text()):
            row = dict(row)
            row["event_type"] = event_type
            row["region"] = region
            rows.append(row)

    if not rows:
        return

    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump(rows, f)
        tmp_path = f.name

    conn.execute("DROP TABLE IF EXISTS raw.raw_events_tmp")
    conn.execute(
        "CREATE TABLE raw.raw_events_tmp AS SELECT * FROM read_json_auto(?)",
        [tmp_path],
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS raw.raw_events AS
        SELECT * FROM raw.raw_events_tmp LIMIT 0
        """
    )
    conn.execute(
        "DELETE FROM raw.raw_events WHERE region = ?",
        [region],
    )
    conn.execute("INSERT INTO raw.raw_events SELECT * FROM raw.raw_events_tmp")
    conn.execute("DROP TABLE raw.raw_events_tmp")
    Path(tmp_path).unlink()


def load_fishing_effort(conn: duckdb.DuckDBPyConnection, region: str) -> None:
    """Load the cached fishing_effort.json file for a region into raw_fishing_effort."""
    path = GFW_RAW_DIR / region / "fishing_effort.json"
    if not path.exists():
        return

    conn.execute("CREATE SCHEMA IF NOT EXISTS raw")
    rows = [dict(row, region=region) for row in json.loads(path.read_text())]
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump(rows, f)
        tmp_path = f.name
    conn.execute(
        "CREATE OR REPLACE TABLE raw.raw_fishing_effort AS SELECT * FROM read_json_auto(?)",
        [tmp_path],
    )
    Path(tmp_path).unlink()


def load_mpas(conn: duckdb.DuckDBPyConnection, region: str) -> None:
    """Load the cached WDPA GeoJSON for a region into raw_mpas using the spatial extension."""
    path = WDPA_RAW_DIR / f"{region}.geojson"
    if not path.exists():
        return

    conn.execute("CREATE SCHEMA IF NOT EXISTS raw")
    conn.execute("INSTALL spatial")
    conn.execute("LOAD spatial")
    conn.execute(
        "CREATE OR REPLACE TABLE raw.raw_mpas AS "
        "SELECT *, ? AS region FROM ST_Read(?)",
        [region, str(path)],
    )


def load_all(region: str, duckdb_path: Path = DUCKDB_PATH) -> None:
    """Load every cached raw source for a region into the DuckDB raw schema."""
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(duckdb_path))
    try:
        load_events(conn, region)
        load_fishing_effort(conn, region)
        load_mpas(conn, region)
    finally:
        conn.close()


if __name__ == "__main__":
    from iuu_radar.config import load_regions

    for _region in load_regions():
        load_all(_region)
