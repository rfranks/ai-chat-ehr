"""Resilience helpers for anonymizer pipelines.

Provides reusable retry orchestration primitives powered by Tenacity so that
pipeline components can make outbound calls with consistent backoff policies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Iterable, TypeVar

from tenacity import (  # type: ignore[import-not-found]
    AsyncRetrying,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    """Configuration for Tenacity retry execution."""

    attempts: int = 3
    initial_delay: float = 0.2
    max_delay: float = 2.0
    backoff_multiplier: float = 2.0
    retry_exceptions: tuple[type[BaseException], ...] = (Exception,)


def _coerce_exceptions(
    exceptions: Iterable[type[BaseException]] | tuple[type[BaseException], ...]
) -> tuple[type[BaseException], ...]:
    """Ensure ``exceptions`` is a tuple for Tenacity configuration."""

    if isinstance(exceptions, tuple):
        return exceptions
    return tuple(exceptions)


def call_with_retry(
    func: Callable[..., T],
    *args: Any,
    policy: RetryPolicy | None = None,
    **kwargs: Any,
) -> T:
    """Execute ``func`` with Tenacity retry semantics."""

    resolved_policy = policy or RetryPolicy()
    retrying = Retrying(
        retry=retry_if_exception_type(
            _coerce_exceptions(resolved_policy.retry_exceptions)
        ),
        stop=stop_after_attempt(resolved_policy.attempts),
        wait=wait_exponential(
            multiplier=resolved_policy.initial_delay,
            min=resolved_policy.initial_delay,
            max=resolved_policy.max_delay,
            exp_base=resolved_policy.backoff_multiplier,
        ),
        reraise=True,
    )

    for attempt in retrying:
        with attempt:
            return func(*args, **kwargs)

    # The loop always returns or raises, but mypy requires an explicit return.
    raise RuntimeError("Retry loop terminated without executing the function.")


async def call_async_with_retry(
    func: Callable[..., Awaitable[T]],
    *args: Any,
    policy: RetryPolicy | None = None,
    **kwargs: Any,
) -> T:
    """Execute async ``func`` with Tenacity retry semantics."""

    resolved_policy = policy or RetryPolicy()
    retrying = AsyncRetrying(
        retry=retry_if_exception_type(
            _coerce_exceptions(resolved_policy.retry_exceptions)
        ),
        stop=stop_after_attempt(resolved_policy.attempts),
        wait=wait_exponential(
            multiplier=resolved_policy.initial_delay,
            min=resolved_policy.initial_delay,
            max=resolved_policy.max_delay,
            exp_base=resolved_policy.backoff_multiplier,
        ),
        reraise=True,
    )

    async for attempt in retrying:
        with attempt:
            return await func(*args, **kwargs)

    raise RuntimeError("Async retry loop terminated without executing the function.")


__all__ = ["RetryPolicy", "call_with_retry", "call_async_with_retry"]
