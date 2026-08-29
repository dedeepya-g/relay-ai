"""FastAPI entrypoint for the Relay backend.

Run locally:
    uvicorn main:app --reload --port 8080

On Cloud Run the container starts the same app against ``$PORT``.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from config import configure_logging, get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Configure logging and announce startup and shutdown."""
    configure_logging()
    settings = get_settings()
    logger.info(
        "Relay API starting (environment=%s, campus=%s)",
        settings.environment,
        settings.campus_id,
    )
    yield
    logger.info("Relay API shutting down")


def create_app() -> FastAPI:
    """Build the FastAPI application.

    Settings are read here rather than inside request handlers, so a missing
    environment variable fails the Cloud Run revision at startup instead of
    surfacing as a 500 on the first request.
    """
    application = FastAPI(
        title="Relay API",
        description="AI campus facilities coordination agent for Relay University.",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(get_settings().allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type"],
    )
    application.include_router(router)
    return application


app = create_app()


@app.get("/healthz", tags=["system"])
def health_check() -> dict[str, str]:
    """Liveness probe used by Cloud Run and the frontend's connection check."""
    return {"status": "ok", "service": "relay-api"}
