"""Patient Context service placeholder application."""

from fastapi import FastAPI

SERVICE_NAME = "patient_context"

app = FastAPI(title="Patient Context Service")


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
        "services.patient_context.main:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
    )
