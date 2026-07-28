"""Shared FastAPI dependencies: read-only DuckDB connection and settings."""

from __future__ import annotations

from functools import lru_cache

import duckdb

from iuu_radar.config import REPO_ROOT, Settings

DUCKDB_PATH = REPO_ROOT / "data" / "processed" / "iuu_radar.duckdb"

# Hard bounds enforced on every list endpoint so a caller cannot trigger an
# expensive or unbounded query (section 11.4 of CLAUDE.md).
MAX_LIMIT = 200
MAX_BBOX_AREA_DEG2 = 400.0  # roughly a 20x20 degree box


@lru_cache
def get_settings() -> Settings:
    """Return cached process-wide settings loaded from the environment."""
    return Settings()


def get_read_only_connection() -> duckdb.DuckDBPyConnection:
    """Open a read-only DuckDB connection. The API must never write result tables."""
    conn = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    try:
        yield conn
    finally:
        conn.close()
