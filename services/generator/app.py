"""Generator FastAPI application providing content generation capabilities."""

from __future__ import annotations

from fastapi import FastAPI

from shared.http.errors import register_exception_handlers
from shared.observability.logger import configure_logging
from shared.observability.middleware import (
    CorrelationIdMiddleware,
    RequestTimingMiddleware,
)

SERVICE_NAME = "generator"

configure_logging(service_name=SERVICE_NAME)

app = FastAPI(title="Generator Service")
app.add_middleware(RequestTimingMiddleware)
app.add_middleware(CorrelationIdMiddleware)
register_exception_handlers(app)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Return a basic health response."""

    return {"status": "ok", "service": SERVICE_NAME}


def get_app() -> FastAPI:
    """Return the configured FastAPI application."""

    return app


__all__ = ["app", "get_app", "health"]
