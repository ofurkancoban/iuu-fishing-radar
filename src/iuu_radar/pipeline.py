"""Prefect flow: ingest -> transform -> features -> score -> export -> notify.

Orchestrates every pipeline stage for one or all configured regions. Triggered
by cron on the VPS; retries are applied to the ingest step since it depends on
external, rate-limited APIs.
"""

from __future__ import annotations

from prefect import flow, task

from iuu_radar.config import Settings, load_regions


@task(retries=3, retry_delay_seconds=30)
def ingest_region(region_name: str, region_cfg: dict, settings: Settings) -> None:
    """Run GFW and WDPA ingestion for one region."""
    raise NotImplementedError("Implement in Phase 8: wire ingest/gfw.py and ingest/wdpa.py")


@task
def transform_region(region_name: str) -> None:
    """Run dbt staging and mart models for one region."""
    raise NotImplementedError("Implement in Phase 8: invoke dbt-duckdb")


@task
def build_features(region_name: str, region_cfg: dict) -> None:
    """Build per-vessel and per-cell feature matrices for one region."""
    raise NotImplementedError("Implement in Phase 8: wire features/build.py")


@task
def score_region(region_name: str) -> None:
    """Run rules + anomaly detection and write result tables for one region."""
    raise NotImplementedError("Implement in Phase 8: wire models/ and export/results.py")


@task
def export_tiles(region_name: str) -> None:
    """Export hotspot and MPA pmtiles for one region."""
    raise NotImplementedError("Implement in Phase 8: wire export/tiles.py")


@task
def notify_new_anomalies(region_name: str) -> None:
    """Publish newly written anomalies to the event bus for the live feed."""
    raise NotImplementedError("Implement in Phase 8: wire events/bus.py")


@flow(name="iuu-radar-pipeline")
def run_pipeline(region_name: str | None = None) -> None:
    """Run the full pipeline for one region, or every configured region if none is given."""
    settings = Settings()
    regions = load_regions()
    names = [region_name] if region_name else list(regions.keys())
    for name in names:
        region_cfg = regions[name]
        ingest_region(name, region_cfg, settings)
        transform_region(name)
        build_features(name, region_cfg)
        score_region(name)
        export_tiles(name)
        notify_new_anomalies(name)


if __name__ == "__main__":
    run_pipeline()
