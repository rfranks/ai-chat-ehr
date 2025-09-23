"""Chain Executor service placeholder application."""

from fastapi import FastAPI

SERVICE_NAME = "chain_executor"

app = FastAPI(title="Chain Executor Service")


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
        "services.chain_executor.main:app",
        host="0.0.0.0",
        port=8003,
        reload=True,
    )
