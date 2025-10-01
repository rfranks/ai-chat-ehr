"""FastAPI application providing anonymization capabilities."""

from __future__ import annotations

from fastapi import APIRouter, FastAPI

from shared.http.errors import register_exception_handlers
from shared.observability.logger import configure_logging
from shared.observability.middleware import (
    CorrelationIdMiddleware,
    RequestTimingMiddleware,
)

SERVICE_NAME = "anonymizer"

configure_logging(service_name=SERVICE_NAME)

app = FastAPI(title="Anonymizer Service")
router = APIRouter(prefix="/anonymizer", tags=["anonymizer"])

app.add_middleware(RequestTimingMiddleware)
app.add_middleware(CorrelationIdMiddleware)
register_exception_handlers(app)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Return service health status metadata."""

    return {"status": "ok", "service": SERVICE_NAME}


# Placeholder routers for anonymization endpoints will be added here in the future.
app.include_router(router)


__all__ = ["app", "health"]
