"""FastAPI application entrypoint for the anonymizer service."""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, FastAPI
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AnonymizerSettings(BaseSettings):
    """Application configuration loaded from the environment."""

    service_name: str = Field(
        default="anonymizer",
        description="Human friendly service identifier used in metadata and logging.",
    )

    model_config = SettingsConfigDict(
        env_prefix="ANONYMIZER_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache
def get_settings() -> AnonymizerSettings:
    """Return cached application settings."""

    return AnonymizerSettings()


def create_app(settings: AnonymizerSettings | None = None) -> FastAPI:
    """Create and configure the FastAPI application instance."""

    settings = settings or get_settings()

    application = FastAPI(title="Anonymizer Service")

    router = APIRouter()

    @router.get("/health", summary="Service health check")
    async def health() -> dict[str, str]:
        """Return a simple health status payload for uptime monitoring."""

        return {"status": "ok", "service": settings.service_name}

    application.include_router(router)

    return application


settings = get_settings()
app = create_app(settings=settings)

__all__ = ["app", "settings", "create_app", "get_settings", "AnonymizerSettings"]
