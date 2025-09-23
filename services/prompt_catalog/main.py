"""Application entrypoint for the prompt catalog service."""

from .app import app, get_app

__all__ = ["app", "get_app"]


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(
        "services.prompt_catalog.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
    )
