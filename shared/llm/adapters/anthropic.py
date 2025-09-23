"""Adapter for configuring Anthropic Claude chat models."""

from __future__ import annotations

from typing import Any, Dict, Optional

from shared.config.settings import Settings
from shared.http.errors import ProviderUnavailableError

from ._base import (
    BaseLanguageModel,
    DEFAULT_MAX_RETRIES,
    attach_retry,
    apply_temperature,
    resolve_settings,
)

try:  # pragma: no cover - optional dependency shim
    from langchain.chat_models import ChatAnthropic
except ImportError as exc:  # pragma: no cover
    try:
        from langchain_anthropic import ChatAnthropic  # type: ignore
    except ImportError:  # pragma: no cover
        raise RuntimeError(
            "Anthropic chat support requires the LangChain Anthropic integration."
        ) from exc


def get_chat_model(
    model_name: str,
    *,
    settings: Optional[Settings] = None,
    temperature: Optional[float] = None,
) -> BaseLanguageModel:
    """Return a configured Anthropic chat model instance."""

    resolved_settings = resolve_settings(settings)
    anthropic_settings = resolved_settings.anthropic
    api_key = (anthropic_settings.api_key or "").strip()
    if not api_key:
        raise ProviderUnavailableError(
            "anthropic",
            detail=(
                "Anthropic API key is not configured. Set the ANTHROPIC_API_KEY "
                "environment variable to enable Claude models."
            ),
            reason="missing_api_key",
        )

    kwargs: Dict[str, Any] = {
        "model": model_name,
        "api_key": api_key,
        "anthropic_api_key": api_key,
        "max_retries": DEFAULT_MAX_RETRIES,
    }
    apply_temperature(kwargs, temperature)

    if anthropic_settings.base_url:
        kwargs["base_url"] = anthropic_settings.base_url
        kwargs["anthropic_api_url"] = anthropic_settings.base_url

    model = ChatAnthropic(**kwargs)
    return attach_retry(
        model,
        label=f"anthropic/{model_name}",
        max_attempts=DEFAULT_MAX_RETRIES,
    )


__all__ = ["get_chat_model"]
