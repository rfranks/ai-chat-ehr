"""Adapter for configuring Google Vertex AI chat models."""

from __future__ import annotations

import os
from pathlib import Path
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
    from langchain.chat_models import ChatVertexAI
except ImportError as exc:  # pragma: no cover
    try:
        from langchain_google_vertexai import ChatVertexAI  # type: ignore
    except ImportError:  # pragma: no cover
        raise RuntimeError(
            "Google Vertex AI support requires the langchain-google-vertexai package."
        ) from exc


def _resolve_credentials_path(explicit_path: Optional[str]) -> Optional[str]:
    """Determine a usable credentials file path if one is available."""

    if explicit_path and explicit_path.strip():
        expanded = Path(explicit_path).expanduser()
        if not expanded.exists():
            raise ProviderUnavailableError(
                "vertex",
                detail=(
                    "Vertex AI credentials file configured in VERTEX_CREDENTIALS_FILE "
                    "does not exist."
                ),
                reason="credentials_file_missing",
            )
        return str(expanded)

    env_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if env_path and env_path.strip():
        expanded = Path(env_path).expanduser()
        if not expanded.exists():
            raise ProviderUnavailableError(
                "vertex",
                detail=(
                    "Vertex AI credentials file referenced by GOOGLE_APPLICATION_CREDENTIALS "
                    "does not exist."
                ),
                reason="env_credentials_missing",
            )
        return str(expanded)

    return None


def get_chat_model(
    model_name: str,
    *,
    settings: Optional[Settings] = None,
    temperature: Optional[float] = None,
    has_explicit_model_override: bool = False,
) -> BaseLanguageModel:
    """Return a configured Vertex AI chat model instance."""

    resolved_settings = resolve_settings(settings)
    vertex_settings = resolved_settings.vertex
    project_id = (vertex_settings.project_id or "").strip()
    location = (vertex_settings.location or "").strip()

    if not project_id:
        raise ProviderUnavailableError(
            "vertex",
            detail=(
                "Vertex AI project ID is not configured. Set the VERTEX_PROJECT_ID "
                "environment variable to enable Gemini models."
            ),
            reason="missing_project_id",
        )
    if not location:
        raise ProviderUnavailableError(
            "vertex",
            detail=(
                "Vertex AI location is not configured. Set the VERTEX_LOCATION environment "
                "variable to enable Gemini models."
            ),
            reason="missing_location",
        )

    resolved_model_name = model_name
    if not has_explicit_model_override and vertex_settings.model:
        resolved_model_name = vertex_settings.model

    credentials_path = _resolve_credentials_path(vertex_settings.credentials_file)
    if credentials_path is None and not os.environ.get("GOOGLE_CLOUD_PROJECT"):
        raise ProviderUnavailableError(
            "vertex",
            detail=(
                "Vertex AI credentials are not configured. Provide VERTEX_CREDENTIALS_FILE "
                "or set GOOGLE_APPLICATION_CREDENTIALS to a service account key."
            ),
            reason="missing_credentials",
        )

    kwargs: Dict[str, Any] = {
        "model_name": resolved_model_name,
        "project": project_id,
        "location": location,
        "max_retries": DEFAULT_MAX_RETRIES,
    }
    apply_temperature(kwargs, temperature)

    if credentials_path:
        kwargs["credentials_path"] = credentials_path

    model = ChatVertexAI(**kwargs)
    return attach_retry(
        model,
        label=f"vertex/{resolved_model_name}",
        max_attempts=DEFAULT_MAX_RETRIES,
    )


__all__ = ["get_chat_model"]
