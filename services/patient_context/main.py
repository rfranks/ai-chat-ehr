"""Entrypoint module for running the Patient Context FastAPI service."""

from __future__ import annotations

from fastapi import FastAPI

from .app import app

__all__ = ["app", "get_app"]


def get_app() -> FastAPI:
    """Return the configured FastAPI application."""

    return app


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(
        "services.patient_context.main:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
    )
