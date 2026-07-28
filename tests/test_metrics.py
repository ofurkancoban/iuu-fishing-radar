"""Unit tests for pipeline run metrics: written by export/results.py, read back
by metrics.refresh_pipeline_gauges into Prometheus gauges."""

from __future__ import annotations

import duckdb

from iuu_radar.export.results import write_pipeline_run
from iuu_radar.metrics import PIPELINE_LAST_RUN_ANOMALIES, refresh_pipeline_gauges


def test_refresh_pipeline_gauges_uses_latest_run_per_region():
    conn = duckdb.connect(":memory:")
    write_pipeline_run(conn, "default", rows_processed=10, anomalies_count=2,
                        duration_seconds=5.0, failed=False)
    write_pipeline_run(conn, "default", rows_processed=20, anomalies_count=7,
                        duration_seconds=8.0, failed=False)

    refresh_pipeline_gauges(conn)

    value = PIPELINE_LAST_RUN_ANOMALIES.labels(region="default")._value.get()
    assert value == 7
    conn.close()


def test_refresh_pipeline_gauges_noop_without_table():
    conn = duckdb.connect(":memory:")
    refresh_pipeline_gauges(conn)  # must not raise
    conn.close()
