"""Custom Prometheus metrics for the pipeline (anomalies per run, rows processed,
run duration, failures).

The pipeline runs as a one-shot batch job (`docker compose run --rm pipeline`),
not a long-lived process, so Prometheus's pull model cannot scrape it directly.
Instead the pipeline appends one row per run to the `pipeline_runs` DuckDB
table (export/results.py:write_pipeline_run), and the long-lived API process
reads the latest row per region on every /metrics scrape and republishes it as
gauges. The API's own HTTP metrics are added separately in api/main.py via
prometheus-fastapi-instrumentator.
"""

from __future__ import annotations

import duckdb
from prometheus_client import Gauge

PIPELINE_LAST_RUN_ANOMALIES = Gauge(
    "iuu_radar_pipeline_last_run_anomalies",
    "New anomalies written to result_anomalies in the most recent pipeline run.",
    ["region"],
)

PIPELINE_LAST_RUN_ROWS_PROCESSED = Gauge(
    "iuu_radar_pipeline_last_run_rows_processed",
    "Rows processed in the most recent pipeline run.",
    ["region"],
)

PIPELINE_LAST_RUN_DURATION_SECONDS = Gauge(
    "iuu_radar_pipeline_last_run_duration_seconds",
    "Wall-clock duration of the most recent pipeline run.",
    ["region"],
)

PIPELINE_LAST_RUN_FAILED = Gauge(
    "iuu_radar_pipeline_last_run_failed",
    "1 if the most recent pipeline run failed, 0 otherwise.",
    ["region"],
)

PIPELINE_LAST_RUN_TIMESTAMP = Gauge(
    "iuu_radar_pipeline_last_run_timestamp_seconds",
    "Unix timestamp of the most recent pipeline run.",
    ["region"],
)


def refresh_pipeline_gauges(conn: duckdb.DuckDBPyConnection) -> None:
    """Read the latest pipeline_runs row per region and update the gauges above."""
    table_exists = conn.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name = 'pipeline_runs'"
    ).fetchone()[0]
    if not table_exists:
        return

    rows = conn.execute(
        """
        SELECT region, rows_processed, anomalies_count, duration_seconds, failed, ts
        FROM pipeline_runs
        QUALIFY row_number() OVER (PARTITION BY region ORDER BY ts DESC) = 1
        """
    ).fetchall()

    for region, rows_processed, anomalies_count, duration_seconds, failed, ts in rows:
        PIPELINE_LAST_RUN_ROWS_PROCESSED.labels(region=region).set(rows_processed)
        PIPELINE_LAST_RUN_ANOMALIES.labels(region=region).set(anomalies_count)
        PIPELINE_LAST_RUN_DURATION_SECONDS.labels(region=region).set(duration_seconds)
        PIPELINE_LAST_RUN_FAILED.labels(region=region).set(1 if failed else 0)
        PIPELINE_LAST_RUN_TIMESTAMP.labels(region=region).set(ts.timestamp())
