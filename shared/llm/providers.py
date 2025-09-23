"""Definitions for supported large language model providers."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Optional

from shared.config.settings import Settings

try:  # pragma: no cover - runtime dependency optional during type checking
    from langchain_core.language_models import BaseLanguageModel
except ImportError:  # pragma: no cover
    try:  # Fallback for pre ``langchain-core`` package layouts.
        from langchain.schema.language_model import BaseLanguageModel  # type: ignore
    except ImportError:  # pragma: no cover
        BaseLanguageModel = Any  # type: ignore[misc,assignment]

if TYPE_CHECKING:  # pragma: no cover
    from .llmmodels import ModelSpec


class LLMProvider(str, Enum):
    """Enumerate supported provider/model combinations."""

    OPENAI_GPT_35_TURBO = "openai/gpt-3.5-turbo"
    OPENAI_GPT_4O = "openai/gpt-4o"
    OPENAI_GPT_4O_MINI = "openai/gpt-4o-mini"
    AZURE_GPT_4O = "azure/gpt-4o"
    AZURE_GPT_4O_MINI = "azure/gpt-4o-mini"
    CLAUDE_3_HAIKU = "anthropic/claude-3-haiku"
    CLAUDE_3_SONNET = "anthropic/claude-3-sonnet"
    GEMINI_25_PRO = "vertex/gemini-2.5-pro"
    GEMINI_25_FLASH = "vertex/gemini-2.5-flash"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value

    @property
    def backend(self) -> str:
        """Return the backend identifier (e.g. ``openai`` or ``azure``)."""

        return self.value.split("/", 1)[0]

    def create_client(
        self,
        settings: Settings,
        temperature: Optional[float] = None,
        model_override: Optional[str] = None,
    ) -> BaseLanguageModel:
        """Instantiate a LangChain client for the provider."""

        from .llmmodels import get_model_spec, resolve_model_spec

        spec = resolve_model_spec(model_override, provider_hint=self)
        if spec.provider is not self:
            if model_override:
                return spec.provider.create_client(
                    settings=settings,
                    temperature=temperature,
                    model_override=model_override,
                )
            spec = get_model_spec(self)

        resolved_temperature = (
            temperature
            if temperature is not None
            else settings.default_model.temperature
        )
        has_override = bool(model_override and model_override.strip())
        backend = spec.backend.lower()

        if backend == "openai":
            return _build_openai_client(settings, spec.model_name, resolved_temperature)
        if backend == "azure":
            return _build_azure_client(settings, spec, resolved_temperature, has_override)
        if backend == "anthropic":
            return _build_anthropic_client(settings, spec.model_name, resolved_temperature)
        if backend in {"vertex", "gemini", "google"}:
            return _build_vertex_client(settings, spec, resolved_temperature, has_override)

        raise ValueError(f"Unsupported LLM backend '{spec.backend}' for provider {self.value}.")


def _maybe_add_temperature(kwargs: Dict[str, Any], temperature: Optional[float]) -> None:
    """Attach ``temperature`` to ``kwargs`` when explicitly provided."""

    if temperature is not None:
        kwargs["temperature"] = float(temperature)


def _build_openai_client(
    settings: Settings,
    model_name: str,
    temperature: Optional[float],
) -> BaseLanguageModel:
    """Create a ChatOpenAI client instance."""

    try:  # pragma: no cover - import depends on optional extras
        from langchain.chat_models import ChatOpenAI
    except ImportError as exc:  # pragma: no cover
        try:
            from langchain_openai import ChatOpenAI  # type: ignore
        except ImportError:
            raise RuntimeError(
                "OpenAI chat support requires the LangChain OpenAI integration."
            ) from exc

    openai_settings = settings.openai
    kwargs: Dict[str, Any] = {
        "model_name": model_name,
        "model": model_name,
    }
    _maybe_add_temperature(kwargs, temperature)
    if openai_settings.api_key:
        kwargs["api_key"] = openai_settings.api_key
        kwargs["openai_api_key"] = openai_settings.api_key
    if openai_settings.organization:
        kwargs["organization"] = openai_settings.organization
        kwargs["openai_organization"] = openai_settings.organization
    if openai_settings.project:
        kwargs["project"] = openai_settings.project
    if openai_settings.base_url:
        kwargs["base_url"] = openai_settings.base_url
        kwargs["openai_api_base"] = openai_settings.base_url
    return ChatOpenAI(**kwargs)


def _build_azure_client(
    settings: Settings,
    spec: "ModelSpec",
    temperature: Optional[float],
    has_override: bool,
) -> BaseLanguageModel:
    """Create an Azure OpenAI chat client instance."""

    try:  # pragma: no cover - optional dependency
        from langchain.chat_models import AzureChatOpenAI
    except ImportError as exc:  # pragma: no cover
        try:
            from langchain_openai import AzureChatOpenAI  # type: ignore
        except ImportError:
            raise RuntimeError(
                "Azure OpenAI chat support requires the LangChain OpenAI integration."
            ) from exc

    azure_settings = settings.azure
    deployment = spec.model_name
    if not has_override and azure_settings.deployment_name:
        deployment = azure_settings.deployment_name
    if not deployment:
        raise ValueError("Azure OpenAI deployment name is required to build a client.")

    kwargs: Dict[str, Any] = {
        "azure_deployment": deployment,
        "deployment_name": deployment,
    }
    _maybe_add_temperature(kwargs, temperature)
    if azure_settings.api_key:
        kwargs["api_key"] = azure_settings.api_key
        kwargs["openai_api_key"] = azure_settings.api_key
    if azure_settings.endpoint:
        kwargs["azure_endpoint"] = azure_settings.endpoint
        kwargs["openai_api_base"] = azure_settings.endpoint
        kwargs["base_url"] = azure_settings.endpoint
    if azure_settings.api_version:
        kwargs["openai_api_version"] = azure_settings.api_version
        kwargs["api_version"] = azure_settings.api_version
    return AzureChatOpenAI(**kwargs)


def _build_anthropic_client(
    settings: Settings,
    model_name: str,
    temperature: Optional[float],
) -> BaseLanguageModel:
    """Create a ChatAnthropic client instance."""

    try:  # pragma: no cover - optional dependency
        from langchain.chat_models import ChatAnthropic
    except ImportError as exc:  # pragma: no cover
        try:
            from langchain_anthropic import ChatAnthropic  # type: ignore
        except ImportError:
            raise RuntimeError(
                "Anthropic chat support requires the LangChain Anthropic integration."
            ) from exc

    anthropic_settings = settings.anthropic
    kwargs: Dict[str, Any] = {"model": model_name}
    _maybe_add_temperature(kwargs, temperature)
    if anthropic_settings.api_key:
        kwargs["api_key"] = anthropic_settings.api_key
        kwargs["anthropic_api_key"] = anthropic_settings.api_key
    if anthropic_settings.base_url:
        kwargs["base_url"] = anthropic_settings.base_url
        kwargs["anthropic_api_url"] = anthropic_settings.base_url
    return ChatAnthropic(**kwargs)


def _build_vertex_client(
    settings: Settings,
    spec: "ModelSpec",
    temperature: Optional[float],
    has_override: bool,
) -> BaseLanguageModel:
    """Create a Vertex AI Gemini chat client instance."""

    try:  # pragma: no cover - optional dependency
        from langchain.chat_models import ChatVertexAI
    except ImportError:
        try:
            from langchain_google_vertexai import ChatVertexAI  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Google Vertex AI support requires the langchain-google-vertexai package."
            ) from exc

    vertex_settings = settings.vertex
    model_name = spec.model_name
    if not has_override and vertex_settings.model:
        model_name = vertex_settings.model

    kwargs: Dict[str, Any] = {"model_name": model_name}
    _maybe_add_temperature(kwargs, temperature)
    if vertex_settings.project_id:
        kwargs["project"] = vertex_settings.project_id
    if vertex_settings.location:
        kwargs["location"] = vertex_settings.location
    if vertex_settings.credentials_file:
        kwargs["credentials_path"] = vertex_settings.credentials_file
    return ChatVertexAI(**kwargs)


__all__ = ["LLMProvider"]
