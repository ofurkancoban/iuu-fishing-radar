"""Build mart_events_mpa (event -> proximity zone) in bounded-size batches.

This used to be a single dbt SQL model joining every event in a region
against every nearby MPA in one shot. That OOM-killed the pipeline on a busy
region (North Sea): DuckDB's memory_limit setting bounds its own buffer
manager, but the spatial extension's R-tree/GEOS-backed intersection tests
allocate memory outside that tracked pool, so a single huge join could still
exceed the host's RAM regardless of the configured limit. Processing events
in fixed-size batches bounds peak memory to one batch's working set,
independent of how many events the region has in total.
"""

from __future__ import annotations

import duckdb

DEFAULT_BATCH_SIZE = 2_000

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS mart_events_mpa (
    event_id VARCHAR,
    region VARCHAR,
    event_type VARCHAR,
    start_ts TIMESTAMP,
    end_ts TIMESTAMP,
    lat DOUBLE,
    lon DOUBLE,
    vessel_id VARCHAR,
    vessel_flag VARCHAR,
    mpa_id VARCHAR,
    mpa_name VARCHAR,
    proximity_zone VARCHAR
)
"""

_BATCH_VIEW_SQL = """
CREATE OR REPLACE TEMP VIEW batch_events AS
SELECT *, st_point(lon, lat) AS geom
FROM stg_gfw_events
WHERE region = '{region}'
ORDER BY event_id
LIMIT {limit} OFFSET {offset}
"""

_INSERT_BATCH_SQL = """
INSERT INTO mart_events_mpa
WITH joined AS (
    SELECT
        e.event_id, e.region, e.event_type, e.start_ts, e.end_ts, e.lat, e.lon,
        e.vessel_id, e.vessel_flag, m.mpa_id, m.mpa_name,
        st_contains(m.geom, e.geom) AS is_inside
    FROM batch_events e
    JOIN int_mpa_buffered m
        ON e.region = m.region AND st_intersects(m.geom_buffered, e.geom)
),
ranked AS (
    SELECT *, row_number() OVER (PARTITION BY event_id ORDER BY is_inside DESC) AS rn
    FROM joined
),
matched AS (
    SELECT
        event_id, region, event_type, start_ts, end_ts, lat, lon, vessel_id, vessel_flag,
        mpa_id, mpa_name,
        CASE WHEN is_inside THEN 'inside' ELSE 'edge' END AS proximity_zone
    FROM ranked
    WHERE rn = 1
),
unmatched AS (
    SELECT
        e.event_id, e.region, e.event_type, e.start_ts, e.end_ts, e.lat, e.lon,
        e.vessel_id, e.vessel_flag,
        CAST(NULL AS VARCHAR) AS mpa_id, CAST(NULL AS VARCHAR) AS mpa_name,
        'outside' AS proximity_zone
    FROM batch_events e
    LEFT JOIN matched mt ON e.event_id = mt.event_id
    WHERE mt.event_id IS NULL
)
SELECT * FROM matched
UNION ALL
SELECT * FROM unmatched
"""


def build_mart_events_mpa(
    conn: duckdb.DuckDBPyConnection, region: str, batch_size: int = DEFAULT_BATCH_SIZE
) -> None:
    """Populate mart_events_mpa for one region, processing events in batches.

    Replaces any existing rows for the region (safe to rerun). Requires
    stg_gfw_events and int_mpa_buffered to already exist (built by dbt).
    """
    conn.execute(_CREATE_TABLE_SQL)
    conn.execute("DELETE FROM mart_events_mpa WHERE region = ?", [region])

    total = conn.execute(
        "SELECT count(*) FROM stg_gfw_events WHERE region = ?", [region]
    ).fetchone()[0]

    if "'" in region:
        raise ValueError("region must not contain a single quote")

    offset = 0
    while offset < total:
        conn.execute(_BATCH_VIEW_SQL.format(region=region, limit=batch_size, offset=offset))
        conn.execute(_INSERT_BATCH_SQL)
        offset += batch_size
