"""Logging helpers integrating structlog and loguru with request context."""

from __future__ import annotations

import logging
import sys
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable, Iterator, Mapping
from types import FrameType

import structlog
from loguru import logger as loguru_logger

__all__ = [
    "configure_logging",
    "generate_request_id",
    "get_logger",
    "get_request_id",
    "request_context",
]

_REQUEST_ID: ContextVar[str | None] = ContextVar("request_id", default=None)
_CONFIGURED: bool = False
_SERVICE_NAME: str | None = None


def _format_record(record: Mapping[str, Any]) -> str:
    """Return the default loguru format string for structured log output."""

    timestamp = record["time"].isoformat()
    level = record["level"].name
    extra = record.get("extra") or {}
    service = extra.get("service", "-")
    request_id = extra.get("request_id") or extra.get("correlation_id") or "-"
    message = record.get("message", "")
    if not isinstance(message, str):
        message = str(message)
    # ``loguru`` expects the return value to still be processed as a
    # ``str.format`` template. Since our structured messages frequently
    # contain JSON payloads, escape curly braces so that the formatter does
    # not treat them as placeholders.
    message = message.replace("{", "{{").replace("}", "}}")
    return f"{timestamp} | {level:<8} | {service} | {request_id} | {message}\n"


def _coerce_level(level: str | int) -> tuple[int, str]:
    """Normalize ``level`` to logging and loguru compatible representations."""

    if isinstance(level, int):
        numeric = level
    else:
        normalized = logging.getLevelName(level.upper())
        if not isinstance(normalized, int):  # pragma: no cover - defensive branch
            raise ValueError(f"Unknown log level: {level}")
        numeric = normalized
    name = logging.getLevelName(numeric)
    if not isinstance(name, str):  # pragma: no cover - defensive branch
        name = "INFO"
    return numeric, name


def get_request_id() -> str | None:
    """Return the request identifier bound to the current context, if any."""

    return _REQUEST_ID.get()


def generate_request_id() -> str:
    """Return a new opaque request identifier."""

    return uuid.uuid4().hex


class LoguruInterceptHandler(logging.Handler):
    """Route standard logging records through Loguru while preserving context."""

    def emit(
        self, record: logging.LogRecord
    ) -> None:  # pragma: no cover - thin wrapper
        level: str | int
        try:
            level = loguru_logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame: FrameType | None = logging.currentframe()
        depth = 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        bound = loguru_logger.bind(logger=record.name)
        request_id = get_request_id()
        if request_id:
            bound = bound.bind(request_id=request_id, correlation_id=request_id)

        bound.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def _configure_structlog() -> None:
    """Configure structlog to emit JSON payloads with context variables."""

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def configure_logging(
    *, service_name: str | None = None, level: str | int = "INFO"
) -> None:
    """Configure loguru/structlog integration for the current process.

    The configuration step is idempotent and safe to call from multiple modules.
    ``service_name`` will be attached to all structured log entries.
    """

    global _CONFIGURED, _SERVICE_NAME

    numeric_level, level_name = _coerce_level(level)

    if not _CONFIGURED:
        loguru_logger.remove()
        loguru_logger.add(
            sys.stdout,
            level=level_name,
            enqueue=True,
            backtrace=False,
            diagnose=False,
            format=_format_record,
        )

        logging.basicConfig(
            handlers=[LoguruInterceptHandler()],
            level=numeric_level,
            force=True,
        )
        logging.captureWarnings(True)

        _configure_structlog()
        _CONFIGURED = True

    if service_name:
        _SERVICE_NAME = service_name
        loguru_logger.configure(extra={"service": service_name})
        structlog.contextvars.bind_contextvars(service=service_name)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structlog bound logger with the given ``name``."""

    if name is None:
        return structlog.get_logger()
    return structlog.get_logger(name)


@contextmanager
def request_context(
    request_id: str | None = None,
    *,
    bind: Callable[..., None] | None = None,
    **extra: Any,
) -> Iterator[str]:
    """Bind ``request_id`` and extra context for the lifetime of the block."""

    if "request_id" in extra:  # pragma: no cover - guard against conflicting kwargs
        extra.pop("request_id")

    rid = request_id or generate_request_id()
    token = _REQUEST_ID.set(rid)
    context_values = dict(extra)
    if _SERVICE_NAME and "service" not in context_values:
        context_values["service"] = _SERVICE_NAME
    correlation = context_values.setdefault("correlation_id", rid)

    context_api = structlog.contextvars
    previous_context = context_api.get_contextvars()

    context_api.bind_contextvars(request_id=rid, **context_values)

    bound_keys = list(dict.fromkeys(["request_id", *context_values.keys()]))

    with loguru_logger.contextualize(
        request_id=rid, correlation_id=correlation, **extra
    ):
        if bind is not None:
            bind()
        try:
            yield rid
        finally:
            context_api.unbind_contextvars(*bound_keys)
            if previous_context:
                restore: dict[str, Any] = {
                    key: previous_context[key]
                    for key in bound_keys
                    if key in previous_context
                }
                if restore:
                    context_api.bind_contextvars(**restore)
            _REQUEST_ID.reset(token)
