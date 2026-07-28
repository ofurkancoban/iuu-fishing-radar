"""Unit tests for the batched events/MPA spatial join (spatial/events_mpa_join.py).

Verifies batching produces the same classification as a single unbatched
pass would, using a synthetic in-memory DuckDB fixture standing in for the
stg_gfw_events / int_mpa_buffered tables dbt normally builds.
"""

from __future__ import annotations

import duckdb

from iuu_radar.spatial.events_mpa_join import build_mart_events_mpa


def _seed(conn: duckdb.DuckDBPyConnection, n_outside_events: int) -> None:
    conn.execute("INSTALL spatial")
    conn.execute("LOAD spatial")

    conn.execute(
        """
        CREATE TABLE int_mpa_buffered AS
        SELECT
            '1' AS mpa_id,
            'default' AS region,
            'Test MPA' AS mpa_name,
            ST_GeomFromText('POLYGON((-91 -1, -90 -1, -90 0, -91 0, -91 -1))') AS geom,
            ST_Buffer(
                ST_GeomFromText('POLYGON((-91 -1, -90 -1, -90 0, -91 0, -91 -1))'),
                10 / 111.0
            ) AS geom_buffered
        """
    )

    rows = [
        # inside the polygon
        ("e_inside", "default", "gap", -0.5, -90.5, "v1"),
        # just south of the boundary, within the 10km buffer -> edge
        ("e_edge", "default", "fishing", -1.005, -90.5, "v2"),
    ]
    for i in range(n_outside_events):
        rows.append((f"e_outside_{i}", "default", "fishing", 10.0, 10.0, "v3"))

    values_sql = ", ".join(
        f"('{eid}', '{region}', '{etype}', TIMESTAMP '2024-01-01', TIMESTAMP '2024-01-01', "
        f"{lat}, {lon}, '{vessel}', 'XXX')"
        for eid, region, etype, lat, lon, vessel in rows
    )
    conn.execute(
        f"""
        CREATE TABLE stg_gfw_events AS
        SELECT * FROM (VALUES {values_sql})
        AS t(event_id, region, event_type, start_ts, end_ts, lat, lon, vessel_id, vessel_flag)
        """
    )


def test_build_mart_events_mpa_classifies_correctly():
    conn = duckdb.connect(":memory:")
    _seed(conn, n_outside_events=3)

    build_mart_events_mpa(conn, "default", batch_size=1000)

    rows = dict(
        conn.execute("SELECT event_id, proximity_zone FROM mart_events_mpa").fetchall()
    )
    assert rows["e_inside"] == "inside"
    assert rows["e_edge"] == "edge"
    assert all(rows[f"e_outside_{i}"] == "outside" for i in range(3))
    conn.close()


def test_build_mart_events_mpa_batching_matches_single_batch():
    conn_batched = duckdb.connect(":memory:")
    _seed(conn_batched, n_outside_events=25)
    build_mart_events_mpa(conn_batched, "default", batch_size=5)
    batched_rows = conn_batched.execute(
        "SELECT event_id, proximity_zone FROM mart_events_mpa ORDER BY event_id"
    ).fetchall()
    conn_batched.close()

    conn_single = duckdb.connect(":memory:")
    _seed(conn_single, n_outside_events=25)
    build_mart_events_mpa(conn_single, "default", batch_size=10_000)
    single_rows = conn_single.execute(
        "SELECT event_id, proximity_zone FROM mart_events_mpa ORDER BY event_id"
    ).fetchall()
    conn_single.close()

    assert batched_rows == single_rows
    assert len(batched_rows) == 27  # inside + edge + 25 outside


def test_build_mart_events_mpa_is_idempotent_per_region():
    conn = duckdb.connect(":memory:")
    _seed(conn, n_outside_events=2)

    build_mart_events_mpa(conn, "default", batch_size=1000)
    build_mart_events_mpa(conn, "default", batch_size=1000)

    total = conn.execute(
        "SELECT count(*) FROM mart_events_mpa WHERE region = 'default'"
    ).fetchone()[0]
    assert total == 4  # inside + edge + 2 outside, not doubled
    conn.close()
