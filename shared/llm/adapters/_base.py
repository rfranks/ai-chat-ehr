"""Shared utilities for LLM adapter implementations."""

from __future__ import annotations

from typing import Any, Dict, Optional

from shared.config.settings import Settings, get_settings

try:  # pragma: no cover - optional dependency shim
    from langchain_core.language_models import BaseLanguageModel
except ImportError:  # pragma: no cover
    try:
        from langchain.schema.language_model import BaseLanguageModel  # type: ignore
    except ImportError:  # pragma: no cover
        BaseLanguageModel = Any  # type: ignore[misc,assignment]

DEFAULT_MAX_RETRIES = 3


def resolve_settings(settings: Optional[Settings]) -> Settings:
    """Return provided settings or fall back to application defaults."""

    return settings or get_settings()


def apply_temperature(kwargs: Dict[str, Any], temperature: Optional[float]) -> None:
    """Attach ``temperature`` to ``kwargs`` when explicitly supplied."""

    if temperature is not None:
        kwargs["temperature"] = float(temperature)


__all__ = [
    "BaseLanguageModel",
    "DEFAULT_MAX_RETRIES",
    "resolve_settings",
    "apply_temperature",
]
