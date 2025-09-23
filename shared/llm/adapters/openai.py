"""Adapter for configuring OpenAI chat models."""

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
    from langchain.chat_models import ChatOpenAI
except ImportError as exc:  # pragma: no cover
    try:
        from langchain_openai import ChatOpenAI  # type: ignore
    except ImportError:  # pragma: no cover
        raise RuntimeError(
            "OpenAI chat support requires the LangChain OpenAI integration."
        ) from exc


def get_chat_model(
    model_name: str,
    *,
    settings: Optional[Settings] = None,
    temperature: Optional[float] = None,
) -> BaseLanguageModel:
    """Return a configured OpenAI chat model instance."""

    resolved_settings = resolve_settings(settings)
    openai_settings = resolved_settings.openai
    api_key = (openai_settings.api_key or "").strip()
    if not api_key:
        raise ProviderUnavailableError(
            "openai",
            detail=(
                "OpenAI API key is not configured. Set the OPENAI_API_KEY environment "
                "variable to enable OpenAI chat models."
            ),
            reason="missing_api_key",
        )

    kwargs: Dict[str, Any] = {
        "model_name": model_name,
        "model": model_name,
        "api_key": api_key,
        "openai_api_key": api_key,
        "max_retries": DEFAULT_MAX_RETRIES,
    }
    apply_temperature(kwargs, temperature)

    if openai_settings.organization:
        kwargs["organization"] = openai_settings.organization
        kwargs["openai_organization"] = openai_settings.organization
    if openai_settings.project:
        kwargs["project"] = openai_settings.project
    if openai_settings.base_url:
        kwargs["base_url"] = openai_settings.base_url
        kwargs["openai_api_base"] = openai_settings.base_url

    model = ChatOpenAI(**kwargs)
    return attach_retry(
        model,
        label=f"openai/{model_name}",
        max_attempts=DEFAULT_MAX_RETRIES,
    )


__all__ = ["get_chat_model"]
