"""Settings definitions for the anonymizer service."""

from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Runtime configuration for the FastAPI application instance."""

    service_name: str = Field(
        default="anonymizer",
        description="Human friendly identifier used in metadata and logging.",
        validation_alias=AliasChoices("ANONYMIZER_SERVICE_NAME", "SERVICE_NAME"),
    )
    host: str = Field(
        default="0.0.0.0",
        description="Hostname or interface the HTTP server binds to.",
        validation_alias=AliasChoices("ANONYMIZER_HOST", "HOST"),
    )
    port: int = Field(
        default=8004,
        description="Port the HTTP server listens on.",
        validation_alias=AliasChoices("ANONYMIZER_PORT", "PORT"),
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class DatabaseSettings(BaseSettings):
    """Database connectivity configuration."""

    url: str = Field(
        default="postgresql+asyncpg://anonymizer:anonymizer@localhost:5432/anonymizer",
        description="SQLAlchemy compatible database URL for anonymizer persistence.",
        validation_alias=AliasChoices("ANONYMIZER_DB_URL", "DATABASE_URL"),
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class LoggingSettings(BaseSettings):
    """Logging configuration for the service."""

    level: str = Field(
        default="info",
        description="Logging verbosity level (e.g. debug, info, warning).",
        validation_alias=AliasChoices("ANONYMIZER_LOG_LEVEL", "LOG_LEVEL"),
    )
    json: bool = Field(
        default=True,
        description="Emit structured JSON logs when set to true.",
        validation_alias=AliasChoices("ANONYMIZER_LOG_JSON", "LOG_JSON"),
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class Settings(BaseSettings):
    """Aggregated settings namespace for the anonymizer service."""

    app: AppSettings = Field(default_factory=AppSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()


__all__ = [
    "AppSettings",
    "DatabaseSettings",
    "LoggingSettings",
    "Settings",
    "get_settings",
]
