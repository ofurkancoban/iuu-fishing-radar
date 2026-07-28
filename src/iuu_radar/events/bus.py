"""Publish/subscribe wrapper for the live anomaly feed.

Default backend is Redis pub/sub. Falls back to a DB-cursor poll (rows in
result_anomalies newer than the last sent id) if Redis is not configured.
Under the optional `streaming` compose profile, Redpanda (Kafka API) can be
used instead; selected by config, documented as a showcase, not a necessity.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from iuu_radar.config import Settings

ANOMALY_CHANNEL = "iuu_radar:anomalies"


class EventBus:
    """Abstract publish/subscribe interface used by the pipeline and the API."""

    async def publish(self, region: str, anomaly: dict) -> None:
        """Publish a newly detected anomaly for a region."""
        raise NotImplementedError("Implement in Phase 6")

    async def subscribe(self, region: str) -> AsyncIterator[dict]:
        """Yield anomalies for a region as they are published."""
        raise NotImplementedError("Implement in Phase 6")


def get_event_bus(settings: Settings) -> EventBus:
    """Return a Redis-backed bus if REDIS_URL is set, otherwise a DB-cursor fallback bus."""
    raise NotImplementedError("Implement in Phase 6")
