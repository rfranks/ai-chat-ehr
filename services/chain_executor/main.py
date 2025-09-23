"""Entrypoint module for the Chain Executor FastAPI service."""

from __future__ import annotations

from fastapi import FastAPI

from .app import app, get_app as _get_app

__all__ = ["app", "get_app"]


def get_app() -> FastAPI:
    """Return the configured FastAPI application."""

    return _get_app()


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(
        "services.chain_executor.main:app",
        host="0.0.0.0",
        port=8003,
        reload=True,
    )
