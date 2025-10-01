"""Consultation models for the generator service."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Iterator, Tuple
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    """Return a naive UTC timestamp compatible with ``timestamp`` columns."""

    return datetime.now(UTC).replace(tzinfo=None)


class ConsultationType(str, Enum):
    """Enumerated values accepted by the ``public.consultation_type`` type."""

    VIDEO_CALL = "VideoCall"
    IN_PERSON = "InPerson"


class BillingStatus(str, Enum):
    """Enumerated values accepted by the ``public.billing_status`` type."""

    PENDING_PROVIDER = "PendingProvider"
    SUBMITTED_TO_QUEUE = "SubmittedToQueue"
    SUBMITTED_TO_BILLING = "SubmittedToBilling"
    SUBMITTED_TO_PAYER = "SubmittedToPayer"
    REJECTED = "Rejected"
    DENIED = "Denied"
    APPROVED = "Approved"
    PAID = "Paid"
    NOT_BILLABLE = "NotBillable"


class AiSoapNoteStatus(str, Enum):
    """Enumerated values accepted by the ``public.ai_soap_note_status`` type."""

    PENDING = "Pending"
    GENERATING = "Generating"
    GENERATED = "Generated"
    CANCELED = "Canceled"
    ERROR = "Error"


class AiSoapNoteError(str, Enum):
    """Enumerated values accepted by the ``public.ai_soap_note_error`` type."""

    TRANSCRIPT_TO_SMALL = "TranscriptToSmall"
    NO_TRANSCRIPT = "NoTranscript"
    API_ERROR = "APIError"
    TIMEOUT = "Timeout"
    CANCELED = "Canceled"
    UNKNOWN = "Unknown"


class SuggestedConfidence(str, Enum):
    """Enumerated values accepted by the ``public.suggested_confidence`` type."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ConsultationCallRequestState(str, Enum):
    """Enumerated values accepted by the ``public.consultation_call_request_state`` type."""

    WAITING = "Waiting"
    RINGING = "Ringing"
    CONNECTED = "Connected"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
    MISSED = "Missed"
    REJECTED = "Rejected"


class ConsultationRecord(BaseModel):
    """Representation of the consultation columns used by the generator."""

    model_config = ConfigDict(populate_by_name=True, validate_assignment=True)

    id: UUID = Field(default_factory=uuid4)
    type: ConsultationType = Field(alias="type", default=ConsultationType.VIDEO_CALL)
    patient_id: UUID = Field(description="Identifier of the patient receiving care")
    facility_id: UUID = Field(description="Identifier of the facility where care occurs")
    nurse_user_id: UUID | None = Field(default=None)
    provider_user_id: UUID | None = Field(default=None)
    chief_complaint: str | None = Field(default=None)
    patient_consent_timestamp: datetime | None = Field(default=None)
    pertinent_exam: Dict[str, Any] | list[Any] | None = Field(default=None)
    short_note: str | None = Field(default=None)
    soap_note: str | None = Field(default=None)
    ai_soap_note: str | None = Field(default=None)
    ai_soap_note_status: AiSoapNoteStatus = Field(
        default=AiSoapNoteStatus.PENDING,
        description="Lifecycle state for the AI-generated SOAP note",
    )
    ai_soap_note_error: AiSoapNoteError | None = Field(default=None)
    order_text: str | None = Field(default=None)
    order_placed_at: datetime | None = Field(default=None)
    order_confirmed_at: datetime | None = Field(default=None)
    provider_signed_at: datetime | None = Field(default=None)
    billing_status: BillingStatus = Field(
        default=BillingStatus.PENDING_PROVIDER,
        description="Billing workflow state maintained by application logic",
    )
    billing_submitted_at: datetime | None = Field(default=None)
    billing_issues: list[str] | None = Field(default=None)
    billing_amount: Decimal | None = Field(default=None)
    candid_instance_id: str | None = Field(default=None)
    candid_encounter_id: str | None = Field(default=None)
    slack_thread_ts: str | None = Field(default=None)
    created_at: datetime = Field(
        default_factory=_utcnow,
        description=(
            "Timestamp automatically set by the database; defaults to CURRENT_TIMESTAMP."
        ),
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        description=(
            "Timestamp maintained by triggers and application updates; defaults to CURRENT_TIMESTAMP."
        ),
    )

    def sql_parameter_items(
        self, *, include_primary_key: bool = True
    ) -> Iterator[Tuple[str, Any]]:
        """Iterate over non-null column/value pairs for SQL operations."""

        column_map: Dict[str, Any] = self.model_dump(by_alias=True)
        for column, value in column_map.items():
            if not include_primary_key and column == "id":
                continue
            if value is None:
                continue
            if isinstance(value, Enum):
                yield column, value.value
            else:
                yield column, value

    def as_sql_parameters(self, *, include_primary_key: bool = True) -> Dict[str, Any]:
        """Return a mapping of column names to non-null SQL parameters."""

        return dict(self.sql_parameter_items(include_primary_key=include_primary_key))


class ConsultationBillingCodeRecord(BaseModel):
    """Representation of the consultation billing code columns."""

    model_config = ConfigDict(populate_by_name=True, validate_assignment=True)

    id: UUID = Field(default_factory=uuid4)
    consultation_id: UUID = Field(description="Identifier of the parent consultation")
    code: str = Field(description="Billing code value")
    description: str = Field(description="Human-readable billing code description")
    suggested: bool = Field(description="Whether the code was suggested by the system")
    suggested_reason: str | None = Field(default=None)
    suggested_confidence: SuggestedConfidence | None = Field(default=None)
    created_at: datetime = Field(
        default_factory=_utcnow,
        description="Timestamp automatically set by the database; defaults to CURRENT_TIMESTAMP.",
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        description="Timestamp maintained by triggers and application updates; defaults to CURRENT_TIMESTAMP.",
    )

    def sql_parameter_items(
        self, *, include_primary_key: bool = True
    ) -> Iterator[Tuple[str, Any]]:
        """Iterate over non-null column/value pairs for SQL operations."""

        column_map: Dict[str, Any] = self.model_dump()
        for column, value in column_map.items():
            if not include_primary_key and column == "id":
                continue
            if value is None:
                continue
            if isinstance(value, Enum):
                yield column, value.value
            else:
                yield column, value

    def as_sql_parameters(self, *, include_primary_key: bool = True) -> Dict[str, Any]:
        """Return a mapping of column names to non-null SQL parameters."""

        return dict(self.sql_parameter_items(include_primary_key=include_primary_key))


class ConsultationCallRequestRecord(BaseModel):
    """Representation of the consultation call request columns."""

    model_config = ConfigDict(populate_by_name=True, validate_assignment=True)

    id: UUID = Field(default_factory=uuid4)
    consultation_id: UUID = Field(description="Identifier of the associated consultation")
    facility_id: UUID = Field(description="Identifier of the facility receiving the call")
    caller_user_id: UUID = Field(description="Identifier of the user initiating the call")
    provider_user_id: UUID | None = Field(default=None)
    call_id: UUID | None = Field(default=None)
    active: bool = Field(
        default=True,
        description="Flag indicating whether the request is the active one for the consultation",
    )
    state: ConsultationCallRequestState = Field(
        default=ConsultationCallRequestState.WAITING,
        description="Lifecycle state for the call request",
    )
    finished_at: datetime | None = Field(default=None)
    created_at: datetime = Field(
        default_factory=_utcnow,
        description="Timestamp automatically set by the database; defaults to CURRENT_TIMESTAMP.",
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        description="Timestamp maintained by triggers and application updates; defaults to CURRENT_TIMESTAMP.",
    )

    def sql_parameter_items(
        self, *, include_primary_key: bool = True
    ) -> Iterator[Tuple[str, Any]]:
        """Iterate over non-null column/value pairs for SQL operations."""

        column_map: Dict[str, Any] = self.model_dump()
        for column, value in column_map.items():
            if not include_primary_key and column == "id":
                continue
            if value is None:
                continue
            if isinstance(value, Enum):
                yield column, value.value
            else:
                yield column, value

    def as_sql_parameters(self, *, include_primary_key: bool = True) -> Dict[str, Any]:
        """Return a mapping of column names to non-null SQL parameters."""

        return dict(self.sql_parameter_items(include_primary_key=include_primary_key))


__all__ = [
    "ConsultationType",
    "BillingStatus",
    "AiSoapNoteStatus",
    "AiSoapNoteError",
    "SuggestedConfidence",
    "ConsultationCallRequestState",
    "ConsultationRecord",
    "ConsultationBillingCodeRecord",
    "ConsultationCallRequestRecord",
]
