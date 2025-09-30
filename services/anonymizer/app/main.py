"""FastAPI application entrypoint for the anonymizer service."""

from __future__ import annotations

from typing import Union

from fastapi import APIRouter, FastAPI

from .config import AppSettings, Settings, get_settings

AppConfig = Union[Settings, AppSettings]


def _extract_app_settings(settings: AppConfig) -> AppSettings:
    """Normalise either top-level or app-only settings objects."""

    if isinstance(settings, Settings):
        return settings.app

    return settings


def create_app(settings: AppConfig | None = None) -> FastAPI:
    """Create and configure the FastAPI application instance."""

    resolved_settings = settings or get_settings()
    app_settings = _extract_app_settings(resolved_settings)

    application = FastAPI(title="Anonymizer Service")

    router = APIRouter()

    @router.get("/health", summary="Service health check")
    async def health() -> dict[str, str]:
        """Return a simple health status payload for uptime monitoring."""

        return {"status": "ok", "service": app_settings.service_name}

    application.include_router(router)

    return application


settings = get_settings()
app = create_app(settings=settings)

__all__ = ["app", "settings", "create_app", "AppSettings", "Settings", "get_settings"]
