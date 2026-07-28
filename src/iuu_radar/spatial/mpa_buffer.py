"""Build int_mpa_buffered (each MPA's buffered, R-tree-indexed geometry) in
bounded Python batches, one region at a time.

This used to be a dbt SQL model (CREATE OR REPLACE TABLE AS SELECT ...) that
recomputed ST_Buffer for every region's MPAs on every run, not just the region
being processed. That grows unbounded as more regions are added, and a single
busy region's MPA set (North Sea: hundreds of large, complex coastal polygons)
was enough on its own to OOM-kill dbt computing ST_Buffer for all of them in
one query. Building the buffer per-region, in batches, and only replacing that
region's rows keeps peak memory bounded and avoids redoing other regions'
work on every run.
"""

from __future__ import annotations

import duckdb

DEFAULT_BATCH_SIZE = 500
EDGE_BUFFER_KM = 10
# 1 degree of latitude is ~111 km; a coarse but dependency-free km->degree
# conversion, adequate for the small-to-regional bboxes this project targets.
EDGE_BUFFER_DEGREES = EDGE_BUFFER_KM / 111.0

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS int_mpa_buffered (
    mpa_id VARCHAR,
    region VARCHAR,
    mpa_name VARCHAR,
    geom GEOMETRY,
    geom_buffered GEOMETRY
)
"""

_INSERT_BATCH_SQL = """
INSERT INTO int_mpa_buffered
SELECT
    mpa_id,
    region,
    mpa_name,
    geom,
    st_buffer(geom, {buffer_degrees}) AS geom_buffered
FROM stg_mpa
WHERE region = '{region}'
ORDER BY mpa_id
LIMIT {limit} OFFSET {offset}
"""


def build_int_mpa_buffered(
    conn: duckdb.DuckDBPyConnection, region: str, batch_size: int = DEFAULT_BATCH_SIZE
) -> None:
    """Populate int_mpa_buffered for one region, buffering MPAs in batches.

    Replaces any existing rows for the region (safe to rerun) and leaves
    every other region's rows untouched. Requires stg_mpa to already exist
    (built by dbt).
    """
    if "'" in region:
        raise ValueError("region must not contain a single quote")

    conn.execute(_CREATE_TABLE_SQL)
    conn.execute("DELETE FROM int_mpa_buffered WHERE region = ?", [region])
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_mpa_buffered_geom "
        "ON int_mpa_buffered USING RTREE (geom_buffered)"
    )

    total = conn.execute(
        "SELECT count(*) FROM stg_mpa WHERE region = ?", [region]
    ).fetchone()[0]

    offset = 0
    while offset < total:
        conn.execute(
            _INSERT_BATCH_SQL.format(
                region=region, buffer_degrees=EDGE_BUFFER_DEGREES, limit=batch_size, offset=offset
            )
        )
        offset += batch_size
