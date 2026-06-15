import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.db import async_session
from app.modules.calls.router import router as calls_router
from app.modules.calls.tasks import expiry_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Run the stale-call expiry scheduler for the lifetime of the server."""
    sweeper = asyncio.create_task(
        expiry_scheduler(
            async_session,
            interval_seconds=settings.expiry_interval_minutes * 60,
            threshold_minutes=settings.expiry_threshold_minutes,
        )
    )
    try:
        yield
    finally:
        sweeper.cancel()
        with suppress(asyncio.CancelledError):
            await sweeper


TAGS_METADATA = [
    {"name": "calls", "description": "List, inspect, annotate, and ingest call records."},
    {"name": "health", "description": "Service liveness probe."},
]

app = FastAPI(
    title=settings.app_name,
    description="Backend API for the Voico Calls Dashboard.",
    version="0.1.0",
    openapi_tags=TAGS_METADATA,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "X-Signature", "X-Timestamp"],
)

app.include_router(calls_router, prefix="/api", tags=["calls"])


@app.get("/health", tags=["health"], summary="Health check")
async def health_check() -> dict:
    """Return ``ok`` while the service is running."""
    return {"status": "ok", "service": settings.app_name}
