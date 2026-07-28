"""Unit tests for the batched MPA buffering (spatial/mpa_buffer.py).

Verifies buffering happens per-region (other regions' rows untouched),
batching produces the same result as a single unbatched pass, and reruns
are idempotent, using a synthetic in-memory DuckDB fixture standing in for
the stg_mpa table dbt normally builds.
"""

from __future__ import annotations

import duckdb

from iuu_radar.spatial.mpa_buffer import build_int_mpa_buffered


def _seed(conn: duckdb.DuckDBPyConnection, region: str, n_mpas: int) -> None:
    conn.execute("INSTALL spatial")
    conn.execute("LOAD spatial")

    values = ", ".join(
        f"('{region}_{i}', '{region}', 'MPA {i}', "
        f"ST_GeomFromText('POLYGON(({i} {i}, {i + 1} {i}, {i + 1} {i + 1}, "
        f"{i} {i + 1}, {i} {i}))'))"
        for i in range(n_mpas)
    )
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS stg_mpa AS
        SELECT * FROM (VALUES {values}) AS t(mpa_id, region, mpa_name, geom)
        WHERE 1 = 0
        """
    )
    conn.execute(f"INSERT INTO stg_mpa VALUES {values}" if n_mpas else "SELECT 1")


def test_build_int_mpa_buffered_produces_buffered_geometry():
    conn = duckdb.connect(":memory:")
    _seed(conn, "default", 3)

    build_int_mpa_buffered(conn, "default", batch_size=1000)

    rows = conn.execute(
        "SELECT mpa_id, ST_Area(geom_buffered) > ST_Area(geom) AS grew "
        "FROM int_mpa_buffered WHERE region = 'default'"
    ).fetchall()
    assert len(rows) == 3
    assert all(grew for _, grew in rows)
    conn.close()


def test_build_int_mpa_buffered_only_touches_its_own_region():
    conn = duckdb.connect(":memory:")
    _seed(conn, "default", 2)
    build_int_mpa_buffered(conn, "default", batch_size=1000)

    _seed(conn, "turkey_seas", 2)
    build_int_mpa_buffered(conn, "turkey_seas", batch_size=1000)

    regions = conn.execute(
        "SELECT region, count(*) FROM int_mpa_buffered GROUP BY region ORDER BY region"
    ).fetchall()
    assert regions == [("default", 2), ("turkey_seas", 2)]
    conn.close()


def test_build_int_mpa_buffered_batching_matches_single_batch():
    conn_batched = duckdb.connect(":memory:")
    _seed(conn_batched, "default", 25)
    build_int_mpa_buffered(conn_batched, "default", batch_size=5)
    batched_ids = sorted(
        r[0] for r in conn_batched.execute("SELECT mpa_id FROM int_mpa_buffered").fetchall()
    )
    conn_batched.close()

    conn_single = duckdb.connect(":memory:")
    _seed(conn_single, "default", 25)
    build_int_mpa_buffered(conn_single, "default", batch_size=10_000)
    single_ids = sorted(
        r[0] for r in conn_single.execute("SELECT mpa_id FROM int_mpa_buffered").fetchall()
    )
    conn_single.close()

    assert batched_ids == single_ids
    assert len(batched_ids) == 25


def test_build_int_mpa_buffered_is_idempotent_per_region():
    conn = duckdb.connect(":memory:")
    _seed(conn, "default", 4)

    build_int_mpa_buffered(conn, "default", batch_size=1000)
    build_int_mpa_buffered(conn, "default", batch_size=1000)

    total = conn.execute(
        "SELECT count(*) FROM int_mpa_buffered WHERE region = 'default'"
    ).fetchone()[0]
    assert total == 4
    conn.close()
