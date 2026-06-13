import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.modules.calls.router import router as calls_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

TAGS_METADATA = [
    {"name": "calls", "description": "List, inspect, annotate, and ingest call records."},
    {"name": "health", "description": "Service liveness probe."},
]

app = FastAPI(
    title=settings.app_name,
    description="Backend API for the Voico Calls Dashboard.",
    version="0.1.0",
    openapi_tags=TAGS_METADATA,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "X-Signature"],
)

app.include_router(calls_router, prefix="/api", tags=["calls"])


@app.get("/health", tags=["health"], summary="Health check")
async def health_check() -> dict:
    """Return ``ok`` while the service is running."""
    return {"status": "ok", "service": settings.app_name}
