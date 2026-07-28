"""FastAPI app entrypoint: CORS, router mounts, health check."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from iuu_radar.api.deps import get_settings

settings = get_settings()

app = FastAPI(title="IUU Fishing Radar API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    """Liveness check and last pipeline run timestamp (stub until Phase 6)."""
    return {"status": "ok", "last_pipeline_run": None}


# Router mounts (routers implemented in Phase 6):
# from iuu_radar.api.routers import anomalies, hotspots, mpas, vessels
# app.include_router(mpas.router)
# app.include_router(hotspots.router)
# app.include_router(vessels.router)
# app.include_router(anomalies.router)
