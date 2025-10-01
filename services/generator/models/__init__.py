"""Data models used by the generator service."""

from .consultation import (
    AiSoapNoteError,
    AiSoapNoteStatus,
    BillingStatus,
    ConsultationBillingCodeRecord,
    ConsultationCallRequestRecord,
    ConsultationCallRequestState,
    ConsultationRecord,
    ConsultationType,
    SuggestedConfidence,
)
from .patient import Gender, PatientRecord, PatientSeed, PatientStatus

__all__ = [
    "AiSoapNoteError",
    "AiSoapNoteStatus",
    "BillingStatus",
    "ConsultationBillingCodeRecord",
    "ConsultationCallRequestRecord",
    "ConsultationCallRequestState",
    "ConsultationRecord",
    "ConsultationType",
    "Gender",
    "PatientRecord",
    "PatientSeed",
    "PatientStatus",
    "SuggestedConfidence",
]
