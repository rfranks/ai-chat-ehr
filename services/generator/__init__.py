"""Generator service package exposing the FastAPI application factory."""

from .app import app, get_app

__all__ = ["app", "get_app"]
