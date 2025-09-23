"""Shared utilities for LLM adapter implementations."""

from __future__ import annotations

import asyncio
from functools import wraps
from typing import Any, Callable, Dict, Optional

from shared.config.settings import Settings, get_settings
from shared.observability.logger import get_logger

try:  # pragma: no cover - optional dependency shim
    from langchain_core.language_models import BaseLanguageModel
except ImportError:  # pragma: no cover
    try:
        from langchain.schema.language_model import BaseLanguageModel  # type: ignore
    except ImportError:  # pragma: no cover
        BaseLanguageModel = Any  # type: ignore[misc,assignment]

from tenacity import (  # type: ignore[import-not-found]
    AsyncRetrying,
    RetryCallState,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

DEFAULT_MAX_RETRIES = 3

logger = get_logger(__name__)

_RETRY_METHODS: dict[str, bool] = {
    "invoke": False,
    "predict": False,
    "generate": False,
    "__call__": False,
    "ainvoke": True,
    "apredict": True,
    "agenerate": True,
}

_RETRY_MARKER = "_chatehr_retry_wrapped"

_retry_condition = retry_if_exception_type(Exception)
try:  # pragma: no cover - asyncio always available during runtime
    _retry_condition = _retry_condition & ~retry_if_exception_type(asyncio.CancelledError)
except Exception:  # pragma: no cover - defensive fallback
    pass


def resolve_settings(settings: Optional[Settings]) -> Settings:
    """Return provided settings or fall back to application defaults."""

    return settings or get_settings()


def apply_temperature(kwargs: Dict[str, Any], temperature: Optional[float]) -> None:
    """Attach ``temperature`` to ``kwargs`` when explicitly supplied."""

    if temperature is not None:
        kwargs["temperature"] = float(temperature)


def _log_retry(label: str, method_name: str, retry_state: RetryCallState) -> None:
    exception = None
    if retry_state.outcome is not None and retry_state.outcome.failed:
        exception = retry_state.outcome.exception()
    wait = getattr(retry_state.next_action, "sleep", None)
    logger.warning(
        "llm_provider_retry",
        provider=label,
        method=method_name,
        attempt=retry_state.attempt_number,
        wait=wait,
        error=str(exception) if exception else None,
    )


def _wrap_with_retry(
    method: Callable[..., Any],
    *,
    is_async: bool,
    label: str,
    max_attempts: int,
) -> Callable[..., Any]:
    method_name = getattr(method, "__name__", "call")

    if is_async:

        @wraps(method)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(multiplier=0.5, min=0.5, max=5.0),
                retry=_retry_condition,
                reraise=True,
                before_sleep=lambda state: _log_retry(label, method_name, state),
            ):
                with attempt:
                    return await method(*args, **kwargs)

        return async_wrapper

    @wraps(method)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        for attempt in Retrying(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=5.0),
            retry=_retry_condition,
            reraise=True,
            before_sleep=lambda state: _log_retry(label, method_name, state),
        ):
            with attempt:
                return method(*args, **kwargs)

    return sync_wrapper


def attach_retry(
    model: BaseLanguageModel,
    *,
    label: str | None = None,
    max_attempts: int = DEFAULT_MAX_RETRIES,
) -> BaseLanguageModel:
    """Wrap key language-model invocation methods with tenacity retry logic."""

    if max_attempts <= 1:
        return model

    if getattr(model, _RETRY_MARKER, False):
        return model

    provider_label = label or model.__class__.__name__

    for method_name, is_async in _RETRY_METHODS.items():
        original = getattr(model, method_name, None)
        if not callable(original):
            continue
        wrapped = _wrap_with_retry(
            original,
            is_async=is_async,
            label=provider_label,
            max_attempts=max_attempts,
        )
        setattr(model, method_name, wrapped)

    setattr(model, _RETRY_MARKER, True)
    return model


__all__ = [
    "BaseLanguageModel",
    "DEFAULT_MAX_RETRIES",
    "resolve_settings",
    "apply_temperature",
    "attach_retry",
]
