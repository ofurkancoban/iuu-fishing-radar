"""Shared FastAPI dependencies: read-only DuckDB connection and settings."""

from __future__ import annotations

from functools import lru_cache

import duckdb

from iuu_radar.config import REPO_ROOT, Settings

DUCKDB_PATH = REPO_ROOT / "data" / "processed" / "iuu_radar.duckdb"


@lru_cache
def get_settings() -> Settings:
    """Return cached process-wide settings loaded from the environment."""
    return Settings()


def get_read_only_connection() -> duckdb.DuckDBPyConnection:
    """Open a read-only DuckDB connection. The API must never write result tables."""
    raise NotImplementedError("Implement in Phase 6")
