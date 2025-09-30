"""Settings definitions for the anonymizer service."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Sequence

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_DDL_DIRECTORY = (
    Path(__file__).resolve().parents[1] / "pipelines" / "ddl"
).resolve()


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


class FirestoreSettings(BaseSettings):
    """Firestore client configuration."""

    project_id: str | None = Field(
        default=None,
        description="Google Cloud project identifier for Firestore.",
        validation_alias=AliasChoices(
            "ANONYMIZER_FIRESTORE_PROJECT_ID", "FIRESTORE_PROJECT_ID"
        ),
    )
    default_collection: str | None = Field(
        default="patients",
        description="Default collection used when fetching patient documents.",
        validation_alias=AliasChoices(
            "ANONYMIZER_FIRESTORE_COLLECTION", "FIRESTORE_COLLECTION"
        ),
    )
    credentials_path: str | None = Field(
        default=None,
        description="Filesystem path to a service account JSON credential.",
        validation_alias=AliasChoices(
            "ANONYMIZER_FIRESTORE_CREDENTIALS_PATH",
            "FIRESTORE_CREDENTIALS_PATH",
        ),
    )
    credentials_info: dict[str, Any] | None = Field(
        default=None,
        description="Dictionary of credential information for Firestore clients.",
        validation_alias=AliasChoices(
            "ANONYMIZER_FIRESTORE_CREDENTIALS_INFO",
            "FIRESTORE_CREDENTIALS_INFO",
        ),
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class PipelineSettings(BaseSettings):
    """Configuration driving anonymization pipeline behaviour."""

    ddl_directory: str = Field(
        default=str(_DEFAULT_DDL_DIRECTORY),
        description="Directory containing .ddl files for pipeline mappings.",
        validation_alias=AliasChoices(
            "ANONYMIZER_PIPELINE_DDL_DIRECTORY", "PIPELINE_DDL_DIRECTORY"
        ),
    )
    include_defaulted: bool = Field(
        default=False,
        description="Include columns with defaults when building INSERT statements.",
        validation_alias=AliasChoices(
            "ANONYMIZER_PIPELINE_INCLUDE_DEFAULTED",
            "PIPELINE_INCLUDE_DEFAULTED",
        ),
    )
    include_nullable: bool = Field(
        default=True,
        description="Include nullable columns when building INSERT statements.",
        validation_alias=AliasChoices(
            "ANONYMIZER_PIPELINE_INCLUDE_NULLABLE",
            "PIPELINE_INCLUDE_NULLABLE",
        ),
    )
    returning: dict[str, Sequence[str]] = Field(
        default_factory=dict,
        description="Mapping of DDL keys to RETURNING clause column names.",
        validation_alias=AliasChoices(
            "ANONYMIZER_PIPELINE_RETURNING", "PIPELINE_RETURNING"
        ),
    )
    patient_collection: str | None = Field(
        default="patients",
        description="Firestore collection storing patient documents.",
        validation_alias=AliasChoices(
            "ANONYMIZER_PIPELINE_PATIENT_COLLECTION",
            "PIPELINE_PATIENT_COLLECTION",
        ),
    )
    patient_ddl_key: str = Field(
        default="patients",
        description="DDL mapping key used for patient anonymization inserts.",
        validation_alias=AliasChoices(
            "ANONYMIZER_PIPELINE_PATIENT_DDL_KEY",
            "PIPELINE_PATIENT_DDL_KEY",
        ),
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class Settings(BaseSettings):
    """Aggregated settings namespace for the anonymizer service."""

    app: AppSettings = Field(default_factory=AppSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    firestore: FirestoreSettings = Field(default_factory=FirestoreSettings)
    pipeline: PipelineSettings = Field(default_factory=PipelineSettings)

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
    "PipelineSettings",
    "FirestoreSettings",
    "Settings",
    "get_settings",
]
