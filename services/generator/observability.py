"""Observability helpers shared by the generator service."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence, Set
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from typing import Any, Iterator

from shared.observability import configure_logging, get_logger, request_context

from .constants import SERVICE_NAME

configure_logging(service_name=SERVICE_NAME)

logger = get_logger("services.generator")


@contextmanager
def cli_request_context(
    *, request_id: str | None = None, **extra: Any
) -> Iterator[str]:
    """Bind a request identifier for CLI-driven workflows.

    The helper ensures multi-step CLI operations attach correlation metadata to
    generated log entries so downstream processors can stitch together related
    events.
    """

    cli_context = {"channel": "cli"}
    cli_context.update(extra)

    with request_context(request_id=request_id, **cli_context) as bound_request_id:
        yield bound_request_id


def scrub_for_logging(
    payload: Any,
    *,
    allow_keys: Iterable[str] | None = None,
    max_depth: int = 3,
    max_items: int = 5,
) -> Any:
    """Return a sanitized representation of ``payload`` safe for log emission.

    Strings and other potentially sensitive scalar values are replaced with a
    ``"[redacted]"`` placeholder unless explicitly opted in through
    ``allow_keys``.  Nested mappings, dataclasses, and Pydantic models are
    traversed up to ``max_depth`` levels to avoid unbounded recursion.  Sequence
    types are summarized to the first ``max_items`` elements to keep log payloads
    compact while still providing useful debugging context.
    """

    allowed = set(allow_keys or set())

    def _scrub(value: Any, depth: int) -> Any:
        if depth <= 0:
            return "[scrubbed]"

        if isinstance(value, Mapping):
            sanitized: dict[str, Any] = {}
            for key, item in value.items():
                key_str = str(key)
                if key_str in allowed:
                    sanitized[key_str] = item
                else:
                    sanitized[key_str] = _scrub(item, depth - 1)
            return sanitized

        if is_dataclass(value):
            return _scrub(asdict(value), depth)

        if hasattr(value, "model_dump"):
            dump = value.model_dump  # type: ignore[attr-defined]
            try:
                mapping = dump(mode="python")  # type: ignore[call-arg]
            except TypeError:  # pragma: no cover - older signatures
                mapping = dump()
            if isinstance(mapping, Mapping):
                return _scrub(mapping, depth)

        if isinstance(value, str):
            return value if not value else "[redacted]"

        if isinstance(value, bytes):
            return "[bytes]"

        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            sample = [_scrub(item, depth - 1) for item in list(value)[:max_items]]
            if isinstance(value, tuple):
                return tuple(sample)
            return sample

        if isinstance(value, Set):
            sample = [_scrub(item, depth - 1) for item in list(value)[:max_items]]
            try:
                return type(value)(sample)
            except TypeError:  # pragma: no cover - fallback for unhashable payloads
                return sample

        if isinstance(value, (int, float, bool)) or value is None:
            return value

        return str(value)

    return _scrub(payload, max_depth)


__all__ = ["cli_request_context", "logger", "scrub_for_logging"]
