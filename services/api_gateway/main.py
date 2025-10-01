"""Entrypoint module for the API Gateway FastAPI service."""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from .app import get_app

app: FastAPI = get_app()

__all__ = ["app", "get_app", "main"]


def main() -> None:
    """Run the API gateway using ``uvicorn``."""

    uvicorn.run(
        "services.api_gateway.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
