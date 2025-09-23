"""Audit helpers for recording chat-related events."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

import structlog

from .logger import get_logger, get_request_id

__all__ = [
    "AuditRepository",
    "ChatAudit",
    "StdoutAuditRepository",
    "get_audit_repository",
    "record_chat_audit",
]


@dataclass(slots=True)
class ChatAudit:
    """Structured payload describing an auditable chat event."""

    event: str
    actor: str | None = None
    subject: str | None = None
    request_id: str | None = None
    session_id: str | None = None
    service: str | None = None
    success: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the audit entry."""

        payload = {
            "event": self.event,
            "actor": self.actor,
            "subject": self.subject,
            "requestId": self.request_id,
            "sessionId": self.session_id,
            "service": self.service,
            "success": self.success,
            "metadata": dict(self.metadata),
            "createdAt": self.created_at.isoformat(),
        }
        return payload


class AuditRepository(Protocol):
    """Abstract repository contract for persisting chat audit events."""

    async def persist(self, audit: ChatAudit) -> None:  # pragma: no cover - interface definition
        """Persist ``audit`` to the underlying storage backend."""


class StdoutAuditRepository:
    """Persist audit entries to the configured logger."""

    def __init__(self) -> None:
        self._logger = get_logger("audit")

    async def persist(self, audit: ChatAudit) -> None:
        payload = audit.to_dict()
        self._logger.info("chat_audit", **payload)


_DEFAULT_REPOSITORY: AuditRepository | None = None


def get_audit_repository() -> AuditRepository:
    """Return the globally configured audit repository."""

    global _DEFAULT_REPOSITORY
    if _DEFAULT_REPOSITORY is None:
        _DEFAULT_REPOSITORY = StdoutAuditRepository()
    return _DEFAULT_REPOSITORY


async def record_chat_audit(
    event: str,
    *,
    actor: str | None = None,
    subject: str | None = None,
    session_id: str | None = None,
    success: bool | None = None,
    metadata: dict[str, Any] | None = None,
    repository: AuditRepository | None = None,
    request_id: str | None = None,
    service: str | None = None,
) -> ChatAudit:
    """Capture an audit event and persist it using the configured repository."""

    repo = repository or get_audit_repository()
    resolved_request_id = request_id or get_request_id()
    context = structlog.contextvars.get_contextvars()
    resolved_service = service or context.get("service")

    audit_entry = ChatAudit(
        event=event,
        actor=actor,
        subject=subject,
        request_id=resolved_request_id,
        session_id=session_id,
        service=resolved_service,
        success=success,
        metadata=dict(metadata or {}),
    )

    await repo.persist(audit_entry)
    return audit_entry
