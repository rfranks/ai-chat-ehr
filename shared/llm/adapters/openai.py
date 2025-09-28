"""Adapter for configuring OpenAI chat models."""

from __future__ import annotations

from typing import Any, Dict, Optional

from shared.config.settings import Settings
from shared.http.errors import ProviderUnavailableError

from ._base import (
    BaseLanguageModel,
    DEFAULT_MAX_RETRIES,
    # attach_retry,
    apply_temperature,
    # ensure_langchain_compat,
    filter_model_kwargs,
    resolve_settings,
)

try:
    from langchain_openai import ChatOpenAI
except ImportError as exc:  # pragma: no cover
    _openai_import_error = exc

    class ChatOpenAI:  # type: ignore[override]
        """Placeholder when ``langchain-openai`` is unavailable."""

        def __init__(
            self, *args: Any, **kwargs: Any
        ) -> None:  # pragma: no cover - stub
            raise RuntimeError(
                "OpenAI chat support requires the langchain-openai package."
            ) from _openai_import_error


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

    candidate_kwargs: Dict[str, Any] = {
        "model": model_name,
        "model_name": model_name,
        "api_key": api_key,
        "openai_api_key": api_key,
        "max_retries": DEFAULT_MAX_RETRIES,
    }
    apply_temperature(candidate_kwargs, temperature)

    if openai_settings.organization:
        candidate_kwargs["organization"] = openai_settings.organization
        candidate_kwargs["openai_organization"] = openai_settings.organization
    if openai_settings.project:
        candidate_kwargs["project"] = openai_settings.project
    if openai_settings.base_url:
        candidate_kwargs["base_url"] = openai_settings.base_url
        candidate_kwargs["openai_api_base"] = openai_settings.base_url

    model_kwargs = filter_model_kwargs(ChatOpenAI, candidate_kwargs)
    model = ChatOpenAI(**model_kwargs)
    # model = ensure_langchain_compat(model)
    # return attach_retry(
    #     model,
    #     label=f"openai/{model_name}",
    #     max_attempts=DEFAULT_MAX_RETRIES,
    # )
    return model


__all__ = ["get_chat_model"]
