"""Prompt Catalog service placeholder application."""

from fastapi import FastAPI

SERVICE_NAME = "prompt_catalog"

app = FastAPI(title="Prompt Catalog Service")


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Return a simple health payload for orchestration checks."""
    return {"status": "ok", "service": SERVICE_NAME}


def get_app() -> FastAPI:
    """Return the FastAPI app instance."""
    return app


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(
        "services.prompt_catalog.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
    )
