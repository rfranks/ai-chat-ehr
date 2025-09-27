"""Adapter for configuring Anthropic Claude chat models."""

from __future__ import annotations

from typing import Any, Dict, Optional, Type

from shared.config.settings import Settings
from shared.http.errors import ProviderUnavailableError

from ._base import (
    BaseLanguageModel,
    DEFAULT_MAX_RETRIES,
    attach_retry,
    apply_temperature,
    filter_model_kwargs,
    resolve_settings,
)

try:
    from langchain_anthropic import ChatAnthropic as _ChatAnthropic
except ImportError as exc:  # pragma: no cover
    _anthropic_import_error = exc

    class _ChatAnthropicPlaceholder:
        """Placeholder when ``langchain-anthropic`` is unavailable."""

        model_fields: Dict[str, Any] = {}

        def __init__(
            self, *args: Any, **kwargs: Any
        ) -> None:  # pragma: no cover - stub
            raise RuntimeError(
                "Anthropic chat support requires the langchain-anthropic package."
            ) from _anthropic_import_error

    ChatAnthropicCls: Type[Any] = _ChatAnthropicPlaceholder
else:  # pragma: no cover - executed when dependency is available
    ChatAnthropicCls = _ChatAnthropic


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

    candidate_kwargs: Dict[str, Any] = {
        "model": model_name,
        "model_name": model_name,
        "api_key": api_key,
        "anthropic_api_key": api_key,
        "max_retries": DEFAULT_MAX_RETRIES,
    }
    apply_temperature(candidate_kwargs, temperature)

    if anthropic_settings.base_url:
        candidate_kwargs["base_url"] = anthropic_settings.base_url
        candidate_kwargs["anthropic_api_url"] = anthropic_settings.base_url

    model_kwargs = filter_model_kwargs(ChatAnthropicCls, candidate_kwargs)
    model = ChatAnthropicCls(**model_kwargs)
    return attach_retry(
        model,
        label=f"anthropic/{model_name}",
        max_attempts=DEFAULT_MAX_RETRIES,
    )


__all__ = ["get_chat_model"]
