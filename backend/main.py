"""FastAPI entrypoint for the Relay backend.

Run locally:
    uvicorn main:app --reload --port 8080

On Cloud Run the container starts the same app against ``$PORT``.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from api.routes import router
from config import configure_logging, get_settings

logger = logging.getLogger(__name__)


class UnhandledErrorMiddleware(BaseHTTPMiddleware):
    """Turn an unhandled exception into a JSON 500 from inside the stack.

    Starlette's own error handling sits *outside* every middleware the
    application adds, so a 500 it generates never passes back through
    ``CORSMiddleware`` and carries no ``Access-Control-Allow-Origin`` header. A
    browser then blocks the response before the page can read it, and a server
    that is running and failing is indistinguishable from one that is not
    running at all -- which sends a reader to restart a healthy server instead
    of to the actual error.

    Catching here, beneath CORS, means the response travels back out through
    that middleware and arrives with the headers it needs.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:  # noqa: BLE001 - deliberately the catch-all
            logger.exception(
                "Unhandled error on %s %s", request.method, request.url.path
            )
            # Outside local development the class and message could name
            # internal detail, so only the generic form crosses the wire.
            detail = (
                f"{type(exc).__name__}: {exc}"
                if get_settings().environment == "local"
                else "Relay hit an unexpected error. Check the server logs."
            )
            return JSONResponse(status_code=500, content={"detail": detail})


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
    # Order matters and is the whole point: `add_middleware` puts each new
    # layer outside the previous one, so adding the catch-all first and CORS
    # second leaves CORS outermost. An error response produced below therefore
    # still passes through CORS on its way out.
    application.add_middleware(UnhandledErrorMiddleware)
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
