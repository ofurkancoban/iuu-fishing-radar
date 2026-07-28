"""Prefect flow: ingest -> transform -> features -> score -> export -> notify.

Orchestrates every pipeline stage for one or all configured regions. Triggered
by cron on the VPS; retries are applied to the ingest step since it depends on
external, rate-limited APIs.
"""

from __future__ import annotations

import subprocess
import time

import duckdb
from prefect import flow, task

from iuu_radar.config import REPO_ROOT, Settings, load_regions
from iuu_radar.export import results as export_results
from iuu_radar.export import tiles as export_tiles_mod
from iuu_radar.features.build import build_cell_features, build_vessel_features
from iuu_radar.ingest import duckdb_raw
from iuu_radar.ingest import gfw as gfw_ingest
from iuu_radar.ingest import wdpa as wdpa_ingest
from iuu_radar.models.anomaly import fit_score, merge_scores
from iuu_radar.models.rules import apply_rules

DBT_PROJECT_DIR = REPO_ROOT / "dbt" / "iuu_radar"


@task(retries=3, retry_delay_seconds=30)
async def ingest_region(region_name: str, region_cfg: dict, settings: Settings) -> None:
    """Run GFW and WDPA ingestion for one region, then load raw caches into DuckDB."""
    await gfw_ingest.fetch_fishing_effort(region_name, region_cfg, settings)
    for event_type in region_cfg["gfw"]["event_types"]:
        await gfw_ingest.fetch_events(region_name, region_cfg, settings, event_type)
    wdpa_ingest.load_mpa_polygons(region_name, region_cfg)
    duckdb_raw.load_all(region_name)


@task
def transform_region(region_name: str) -> None:
    """Run dbt staging and mart models for the whole DuckDB file (dbt has no region filter)."""
    subprocess.run(
        ["dbt", "run", "--profiles-dir", str(DBT_PROJECT_DIR)],
        cwd=DBT_PROJECT_DIR,
        check=True,
    )


@task
def score_region(region_name: str) -> None:
    """Build features, run rules + anomaly detection, and write result tables for one region."""
    conn = duckdb.connect(str(duckdb_raw.DUCKDB_PATH))
    try:
        vessel_features = build_vessel_features(conn, region_name)
        cell_features = build_cell_features(conn, region_name, resolution=6)

        with_rules = apply_rules(vessel_features)
        anomaly_scores = fit_score(vessel_features)
        final_scores = merge_scores(anomaly_scores, with_rules)

        vessels_out = with_rules.assign(score=final_scores, last_seen=None)[
            ["vessel_id", "region", "score", "flags", "reasons", "last_seen"]
        ]
        export_results.write_vessels(conn, vessels_out)
        export_results.write_hotspots(conn, cell_features)

        mpa_scores = (
            vessels_out.groupby("region")["score"]
            .mean()
            .reset_index()
            .assign(mpa_id="aggregate")[["mpa_id", "region", "score"]]
        )
        export_results.write_mpa_scores(conn, mpa_scores)
    finally:
        conn.close()


@task
def export_tiles(region_name: str) -> None:
    """Export hotspot and MPA pmtiles for one region."""
    conn = duckdb.connect(str(duckdb_raw.DUCKDB_PATH), read_only=True)
    try:
        hotspots = conn.execute(
            "SELECT * FROM result_hotspots WHERE region = ?", [region_name]
        ).fetch_df()
    finally:
        conn.close()

    if hotspots.empty:
        return

    geojson_path = REPO_ROOT / "data" / "interim" / f"{region_name}_hotspots.geojson"
    export_tiles_mod.hotspots_to_geojson(hotspots, geojson_path)
    export_tiles_mod.build_hotspot_tiles(geojson_path)

    mpa_geojson = wdpa_ingest.RAW_DIR / f"{region_name}.geojson"
    if mpa_geojson.exists():
        export_tiles_mod.build_mpa_tiles(mpa_geojson)


@task
async def notify_new_anomalies(region_name: str, settings: Settings) -> None:
    """Publish newly written anomalies to the event bus for the live feed."""
    from iuu_radar.events.bus import get_event_bus

    conn = duckdb.connect(str(duckdb_raw.DUCKDB_PATH), read_only=True)
    try:
        rows = conn.execute(
            "SELECT vessel_id, lon, lat, ts, reasons FROM result_anomalies "
            "WHERE region = ? ORDER BY id DESC LIMIT 10",
            [region_name],
        ).fetchall()
    finally:
        conn.close()

    bus = get_event_bus(settings)
    for vessel_id, lon, lat, ts, reasons in rows:
        await bus.publish(
            region_name,
            {"vessel_id": vessel_id, "lon": lon, "lat": lat, "ts": str(ts), "reasons": reasons},
        )


@flow(name="iuu-radar-pipeline")
async def run_pipeline(region_name: str | None = None) -> None:
    """Run the full pipeline for one region, or every configured region if none is given.

    Records one pipeline_runs row per region (rows processed, anomalies
    written, duration, success/failure) for the /metrics gauges in
    metrics.refresh_pipeline_gauges.
    """
    settings = Settings()
    regions = load_regions()
    names = [region_name] if region_name else list(regions.keys())

    for name in names:
        region_cfg = regions[name]
        started = time.monotonic()
        failed = False
        rows_processed = 0
        anomalies_count = 0

        try:
            await ingest_region(name, region_cfg, settings)
            transform_region(name)
            score_region(name)

            conn = duckdb.connect(str(duckdb_raw.DUCKDB_PATH), read_only=True)
            try:
                rows_processed = conn.execute(
                    "SELECT count(*) FROM result_vessels WHERE region = ?", [name]
                ).fetchone()[0]
                anomalies_count = conn.execute(
                    "SELECT count(*) FROM result_anomalies WHERE region = ?", [name]
                ).fetchone()[0]
            finally:
                conn.close()

            export_tiles(name)
            await notify_new_anomalies(name, settings)
        except Exception:
            failed = True
            raise
        finally:
            conn = duckdb.connect(str(duckdb_raw.DUCKDB_PATH))
            try:
                export_results.write_pipeline_run(
                    conn,
                    region=name,
                    rows_processed=rows_processed,
                    anomalies_count=anomalies_count,
                    duration_seconds=time.monotonic() - started,
                    failed=failed,
                )
            finally:
                conn.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_pipeline())
