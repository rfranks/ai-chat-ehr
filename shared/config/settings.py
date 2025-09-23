"""Application configuration powered by ``pydantic-settings``."""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AzureSettings(BaseSettings):
    """Configuration for Azure-based LLM access."""

    api_key: Optional[str] = Field(default=None, description="Azure API key")
    endpoint: Optional[str] = Field(default=None, description="Azure endpoint for OpenAI compatible APIs")
    deployment_name: Optional[str] = Field(default=None, description="Default Azure OpenAI deployment name")
    api_version: Optional[str] = Field(default=None, description="Azure API version")

    model_config = SettingsConfigDict(env_prefix="AZURE_", env_file=".env", extra="ignore")


class OpenAISettings(BaseSettings):
    """Configuration for OpenAI's public API."""

    api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    organization: Optional[str] = Field(default=None, description="OpenAI organization identifier")
    project: Optional[str] = Field(default=None, description="OpenAI project identifier")
    base_url: Optional[str] = Field(default=None, description="Custom OpenAI API base URL override")

    model_config = SettingsConfigDict(env_prefix="OPENAI_", env_file=".env", extra="ignore")


class AnthropicSettings(BaseSettings):
    """Configuration for Anthropic's Claude API."""

    api_key: Optional[str] = Field(default=None, description="Anthropic API key")
    base_url: Optional[str] = Field(default=None, description="Custom Anthropic API base URL override")

    model_config = SettingsConfigDict(env_prefix="ANTHROPIC_", env_file=".env", extra="ignore")


class VertexSettings(BaseSettings):
    """Configuration for Google Vertex AI."""

    project_id: Optional[str] = Field(default=None, description="Google Cloud project identifier")
    location: Optional[str] = Field(default=None, description="Regional location for Vertex AI")
    credentials_file: Optional[str] = Field(default=None, description="Path to Google credentials JSON file")
    model: Optional[str] = Field(default=None, description="Vertex AI model identifier override")

    model_config = SettingsConfigDict(env_prefix="VERTEX_", env_file=".env", extra="ignore")


class ModelDefaults(BaseSettings):
    """Default model selection and behavior."""

    provider: str = Field(default="openai", description="Identifier for the default provider")
    name: str = Field(default="gpt-3.5-turbo", description="Default model name")
    temperature: Optional[float] = Field(default=None, description="Optional default temperature override")

    model_config = SettingsConfigDict(env_prefix="DEFAULT_MODEL_", env_file=".env", extra="ignore")


class Settings(BaseSettings):
    """Top-level application settings namespace."""

    azure: AzureSettings = Field(default_factory=AzureSettings)
    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    anthropic: AnthropicSettings = Field(default_factory=AnthropicSettings)
    vertex: VertexSettings = Field(default_factory=VertexSettings)
    default_model: ModelDefaults = Field(default_factory=ModelDefaults)

    model_config = SettingsConfigDict(env_file=".env", env_nested_delimiter="__", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance for application use."""

    return Settings()


__all__ = [
    "AzureSettings",
    "OpenAISettings",
    "AnthropicSettings",
    "VertexSettings",
    "ModelDefaults",
    "Settings",
    "get_settings",
]
