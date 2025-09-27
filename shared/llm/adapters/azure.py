"""Adapter for configuring Azure OpenAI chat models."""

from __future__ import annotations

from typing import Any, Dict, Optional

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
    from langchain_openai import AzureChatOpenAI
except ImportError as exc:  # pragma: no cover
    _azure_import_error = exc

    class AzureChatOpenAI:  # type: ignore[override]
        """Placeholder when ``langchain-openai`` is unavailable."""

        def __init__(
            self, *args: Any, **kwargs: Any
        ) -> None:  # pragma: no cover - stub
            raise RuntimeError(
                "Azure OpenAI chat support requires the langchain-openai package."
            ) from _azure_import_error


def get_chat_model(
    model_name: str,
    *,
    settings: Optional[Settings] = None,
    temperature: Optional[float] = None,
    has_explicit_model_override: bool = False,
) -> BaseLanguageModel:
    """Return a configured Azure OpenAI chat model instance."""

    resolved_settings = resolve_settings(settings)
    azure_settings = resolved_settings.azure
    api_key = (azure_settings.api_key or "").strip()
    endpoint = (azure_settings.endpoint or "").strip()
    if not api_key:
        raise ProviderUnavailableError(
            "azure",
            detail=(
                "Azure OpenAI API key is not configured. Set the AZURE_API_KEY "
                "environment variable to enable Azure-backed models."
            ),
            reason="missing_api_key",
        )
    if not endpoint:
        raise ProviderUnavailableError(
            "azure",
            detail=(
                "Azure OpenAI endpoint is not configured. Set the AZURE_ENDPOINT "
                "environment variable to enable Azure-backed models."
            ),
            reason="missing_endpoint",
        )

    deployment_name = model_name
    if not has_explicit_model_override and azure_settings.deployment_name:
        deployment_name = azure_settings.deployment_name
    deployment_name = (deployment_name or "").strip()
    if not deployment_name:
        raise ProviderUnavailableError(
            "azure",
            detail=(
                "Azure OpenAI deployment name is not configured. Provide either an "
                "explicit model override or set AZURE_DEPLOYMENT_NAME."
            ),
            reason="missing_deployment",
        )

    candidate_kwargs: Dict[str, Any] = {
        "azure_deployment": deployment_name,
        "deployment_name": deployment_name,
        "model": model_name,
        "model_name": model_name,
        "api_key": api_key,
        "openai_api_key": api_key,
        "azure_api_key": api_key,
        "azure_endpoint": endpoint,
        "openai_api_base": endpoint,
        "base_url": endpoint,
        "max_retries": DEFAULT_MAX_RETRIES,
    }
    apply_temperature(candidate_kwargs, temperature)

    if azure_settings.api_version:
        candidate_kwargs["openai_api_version"] = azure_settings.api_version
        candidate_kwargs["api_version"] = azure_settings.api_version

    model_kwargs = filter_model_kwargs(AzureChatOpenAI, candidate_kwargs)
    model = AzureChatOpenAI(**model_kwargs)
    return attach_retry(
        model,
        label=f"azure/{deployment_name}",
        max_attempts=DEFAULT_MAX_RETRIES,
    )


__all__ = ["get_chat_model"]
