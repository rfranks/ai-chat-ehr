"""Definitions for supported large language model providers."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from shared.config.settings import Settings
from .adapters import (
    anthropic as anthropic_adapter,
    azure as azure_adapter,
    openai as openai_adapter,
    vertex as vertex_adapter,
)

from langchain_core.language_models.base import BaseLanguageModel


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
            return openai_adapter.get_chat_model(
                spec.model_name,
                settings=settings,
                temperature=resolved_temperature,
            )
        if backend == "azure":
            return azure_adapter.get_chat_model(
                spec.model_name,
                settings=settings,
                temperature=resolved_temperature,
                has_explicit_model_override=has_override,
            )
        if backend == "anthropic":
            return anthropic_adapter.get_chat_model(
                spec.model_name,
                settings=settings,
                temperature=resolved_temperature,
            )
        if backend in {"vertex", "gemini", "google"}:
            return vertex_adapter.get_chat_model(
                spec.model_name,
                settings=settings,
                temperature=resolved_temperature,
                has_explicit_model_override=has_override,
            )

        raise ValueError(
            f"Unsupported LLM backend '{spec.backend}' for provider {self.value}."
        )


__all__ = ["LLMProvider"]
