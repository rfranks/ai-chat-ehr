"""Logging utilities for the anonymizer service.

This module wraps the shared observability helpers so the anonymizer service
emits structured JSON logs enriched with correlation identifiers and exposes a
focused audit trail for anonymization actions.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator, Mapping, Sequence

from shared.observability.logger import (
    configure_logging as _base_configure_logging,
    generate_request_id,
    get_logger as _get_logger,
    request_context,
)

__all__ = [
    "ReplacementAuditEntry",
    "AnonymizationAuditEvent",
    "configure_logging",
    "get_logger",
    "anonymizer_logging_context",
    "record_anonymization_audit",
]


_SERVICE_NAME: str | None = None
_AUDIT_LOGGER = _get_logger("anonymizer.audit")


def configure_logging(*, service_name: str, level: str | int = "INFO") -> None:
    """Configure structured logging for the anonymizer service."""

    global _SERVICE_NAME

    _base_configure_logging(service_name=service_name, level=level)
    _SERVICE_NAME = service_name


def get_logger(name: str | None = None):
    """Return a structlog bound logger."""

    return _get_logger(name)


@dataclass(frozen=True, slots=True)
class ReplacementAuditEntry:
    """Summary of the replacements performed for a PHI entity type."""

    entity_type: str
    count: int

    def to_dict(self) -> dict[str, Any]:
        return {"entityType": self.entity_type, "count": self.count}


@dataclass(frozen=True, slots=True)
class AnonymizationAuditEvent:
    """Structured payload describing an anonymization audit record."""

    event: str
    status: str
    document_id: str
    collection: str | None
    actor: str
    total_replacements: int
    replacements: Sequence[ReplacementAuditEntry]
    correlation_id: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat()
    )
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "event": self.event,
            "status": self.status,
            "documentId": self.document_id,
            "collection": self.collection,
            "actor": self.actor,
            "totalReplacements": self.total_replacements,
            "replacements": [item.to_dict() for item in self.replacements],
            "correlationId": self.correlation_id,
            "timestamp": self.timestamp,
            "metadata": dict(self.metadata),
        }
        return payload


@contextmanager
def anonymizer_logging_context(
    *,
    document_id: str | None = None,
    collection: str | None = None,
    correlation_id: str | None = None,
    **extra: Any,
) -> Iterator[str]:
    """Bind anonymizer specific context for the duration of a request."""

    context: dict[str, Any] = dict(extra)
    if document_id:
        context.setdefault("document_id", document_id)
    if collection:
        context.setdefault("collection", collection)

    request_id = correlation_id or generate_request_id()

    with request_context(request_id=request_id, **context) as bound_id:
        yield bound_id


def record_anonymization_audit(
    *,
    document_id: str,
    collection: str | None,
    actor: str | None,
    status: str,
    total_replacements: int,
    replacements: Sequence[ReplacementAuditEntry] | None = None,
    correlation_id: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> AnonymizationAuditEvent:
    """Emit an audit entry capturing anonymization activity."""

    correlation = correlation_id or generate_request_id()
    event_actor = actor or _SERVICE_NAME or "anonymizer"

    audit_event = AnonymizationAuditEvent(
        event="anonymization",
        status=status,
        document_id=document_id,
        collection=collection,
        actor=event_actor,
        total_replacements=total_replacements,
        replacements=tuple(replacements or ()),
        correlation_id=correlation,
        metadata=metadata or {},
    )

    _AUDIT_LOGGER.info("anonymization_audit", **audit_event.to_dict())
    return audit_event
