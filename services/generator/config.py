"""Configuration models for the generator service."""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PostgresSettings(BaseSettings):
    """Settings for the generator service's PostgreSQL storage."""

    dsn: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/generator",
        description="Database connection string used for generator persistence.",
    )

    model_config = SettingsConfigDict(extra="ignore")


class StorageSettings(BaseSettings):
    """Settings describing Google Cloud Storage output destinations."""

    gcs_bucket: Optional[str] = Field(
        default=None,
        description="Name of the Google Cloud Storage bucket for generator artifacts.",
    )
    gcs_prefix: Optional[str] = Field(
        default=None,
        description="Optional key prefix used when writing to the configured bucket.",
    )

    model_config = SettingsConfigDict(extra="ignore")


class ModelOverrideSettings(BaseSettings):
    """Settings for overriding default model selections and behavior."""

    provider: Optional[str] = Field(
        default=None,
        description="Optional provider identifier used when invoking the LLM.",
    )
    name: Optional[str] = Field(
        default=None,
        description="Optional model name override applied to generator prompts.",
    )
    temperature: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Optional temperature override applied to the model invocation.",
    )

    model_config = SettingsConfigDict(extra="ignore")


class GeneratorSettings(BaseSettings):
    """Aggregate configuration for the generator service."""

    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    model_overrides: ModelOverrideSettings = Field(
        default_factory=ModelOverrideSettings
    )
    rng_seed: Optional[int] = Field(
        default=None,
        description="Optional random seed to make generator behaviour deterministic.",
    )

    model_config = SettingsConfigDict(extra="ignore")


class Settings(BaseSettings):
    """Root configuration container enabling nested environment variables."""

    generator: GeneratorSettings = Field(default_factory=GeneratorSettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
    )


@lru_cache
def get_settings() -> GeneratorSettings:
    """Return the cached generator settings instance."""

    return Settings().generator


__all__ = [
    "PostgresSettings",
    "StorageSettings",
    "ModelOverrideSettings",
    "GeneratorSettings",
    "Settings",
    "get_settings",
]
