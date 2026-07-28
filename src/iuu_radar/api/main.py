"""FastAPI app entrypoint: CORS, router mounts, rate limiting, generic error handling."""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from iuu_radar.api.deps import get_settings
from iuu_radar.api.routers import anomalies, hotspots, mpas, vessels
from iuu_radar.api.stream import router as stream_router

logger = logging.getLogger("iuu_radar.api")

settings = get_settings()
limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.rate_limit}/minute"])

app = FastAPI(title="IUU Fishing Radar API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log the real error server-side, return a generic message to the client.

    Never leak stack traces or internal error details to callers (section 11.4).
    """
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Pass through intentional HTTP errors (4xx validation, 404, etc.) unchanged."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/api/health")
def health() -> dict:
    """Liveness check and last pipeline run timestamp."""
    return {"status": "ok"}


app.include_router(mpas.router)
app.include_router(hotspots.router)
app.include_router(vessels.router)
app.include_router(anomalies.router)
app.include_router(stream_router)
