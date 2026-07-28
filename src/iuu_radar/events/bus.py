"""Publish/subscribe wrapper for the live anomaly feed.

Default backend is Redis pub/sub. Falls back to a DB-cursor poll (rows in
result_anomalies newer than the last sent id) if REDIS_URL is not configured.
Under the optional `streaming` compose profile, Redpanda (Kafka API) can be
used instead; selected by config, documented as a showcase, not a necessity.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import duckdb

from iuu_radar.config import Settings

ANOMALY_CHANNEL = "iuu_radar:anomalies"
POLL_INTERVAL_SECONDS = 5


class EventBus:
    """Abstract publish/subscribe interface used by the pipeline and the API."""

    async def publish(self, region: str, anomaly: dict) -> None:
        """Publish a newly detected anomaly for a region."""
        raise NotImplementedError

    async def subscribe(self, region: str) -> AsyncIterator[dict]:
        """Yield anomalies for a region as they are published."""
        raise NotImplementedError
        yield  # pragma: no cover - makes this an async generator for type checkers


class RedisEventBus(EventBus):
    """Publish/subscribe via Redis, decoupling the pipeline process from the API process."""

    def __init__(self, redis_url: str, password: str | None = None) -> None:
        import redis.asyncio as redis

        self._redis = redis.Redis.from_url(redis_url, password=password, decode_responses=True)

    async def publish(self, region: str, anomaly: dict) -> None:
        payload = json.dumps({"region": region, **anomaly})
        await self._redis.publish(ANOMALY_CHANNEL, payload)

    async def subscribe(self, region: str) -> AsyncIterator[dict]:
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(ANOMALY_CHANNEL)
        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                data = json.loads(message["data"])
                if data.get("region") == region:
                    yield data
        finally:
            await pubsub.unsubscribe(ANOMALY_CHANNEL)


class DBCursorEventBus(EventBus):
    """Fallback bus: polls result_anomalies for rows newer than the last sent id.

    publish() is a no-op since new rows are already visible to any poller as
    soon as the pipeline commits them; the "publish" is the DuckDB write itself.
    """

    def __init__(self, duckdb_path: str) -> None:
        self._duckdb_path = duckdb_path

    async def publish(self, region: str, anomaly: dict) -> None:
        return None

    async def subscribe(self, region: str) -> AsyncIterator[dict]:
        last_id = 0
        while True:
            conn = duckdb.connect(self._duckdb_path, read_only=True)
            try:
                rows = conn.execute(
                    """
                    SELECT id, vessel_id, lon, lat, ts, reasons
                    FROM result_anomalies
                    WHERE region = ? AND id > ?
                    ORDER BY id ASC
                    """,
                    [region, last_id],
                ).fetchall()
            finally:
                conn.close()

            for row in rows:
                last_id = row[0]
                yield {
                    "id": row[0],
                    "vessel_id": row[1],
                    "lon": row[2],
                    "lat": row[3],
                    "ts": str(row[4]),
                    "reasons": json.loads(row[5]),
                }

            await asyncio.sleep(POLL_INTERVAL_SECONDS)


def get_event_bus(settings: Settings) -> EventBus:
    """Return a Redis-backed bus if REDIS_URL is set, otherwise a DB-cursor fallback bus."""
    if settings.redis_url:
        return RedisEventBus(settings.redis_url, settings.redis_password)

    from iuu_radar.api.deps import DUCKDB_PATH

    return DBCursorEventBus(str(DUCKDB_PATH))
