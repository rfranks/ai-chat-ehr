"""Observability utilities shared across ChatEHR services."""

from .logger import (
    configure_logging,
    generate_request_id,
    get_logger,
    get_request_id,
    request_context,
)
from .middleware import CorrelationIdMiddleware, RequestTimingMiddleware
from .audit import (
    ChatAudit,
    AuditRepository,
    StdoutAuditRepository,
    get_audit_repository,
    record_chat_audit,
)

__all__ = [
    "AuditRepository",
    "ChatAudit",
    "CorrelationIdMiddleware",
    "RequestTimingMiddleware",
    "StdoutAuditRepository",
    "configure_logging",
    "generate_request_id",
    "get_audit_repository",
    "get_logger",
    "get_request_id",
    "record_chat_audit",
    "request_context",
]
