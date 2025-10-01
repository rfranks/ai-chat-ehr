"""Patient-associated resource models for SQL generation."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from .patient import EHRConnectionStatus, SQLInsertModel, _utcnow


class AllergyCategory(str, Enum):
    """Enumerated values accepted by the ``public.allergy_category`` type."""

    DRUG = "Drug"
    FOOD = "Food"
    ENVIRONMENTAL = "Environmental"
    SUBSTANCE = "Substance"
    OTHER = "Other"
    UNKNOWN = "Unknown"


class AllergyClinicalStatus(str, Enum):
    """Enumerated values accepted by the ``public.allergy_clinical_status`` type."""

    ACTIVE = "Active"
    RESOLVED = "Resolved"
    PRIOR_HISTORY = "PriorHistory"
    UNKNOWN = "Unknown"


class AllergySeverity(str, Enum):
    """Enumerated values accepted by the ``public.allergy_severity`` type."""

    MILD = "Mild"
    MODERATE = "Moderate"
    SEVERE = "Severe"
    UNKNOWN = "Unknown"


class AllergyType(str, Enum):
    """Enumerated values accepted by the ``public.allergy_type`` type."""

    ALLERGY = "Allergy"
    INTOLERANCE = "Intolerance"
    PROPENSITY_TO_ADVERSE_REACTIONS = "PropensityToAdverseReactions"
    UNKNOWN = "Unknown"


class ConditionClinicalStatus(str, Enum):
    """Enumerated values accepted by the ``public.condition_clinical_status`` type."""

    ACTIVE = "Active"
    RESOLVED = "Resolved"
    UNKNOWN = "Unknown"


class MedicationStatus(str, Enum):
    """Enumerated values accepted by the ``public.medication_status`` type."""

    INITIAL = "Initial"
    ACTIVE = "Active"
    ON_HOLD = "OnHold"
    COMPLETED = "Completed"
    DISCONTINUED = "Discontinued"
    STRUCK_OUT = "StruckOut"
    UNVERIFIED = "Unverified"
    UNCONFIRMED = "Unconfirmed"
    PENDING_REVIEW = "PendingReview"
    PENDING_MARK_TO_SIGN = "PendingMarkToSign"
    PENDING_SIGNATURE = "PendingSignature"
    HISTORICAL = "Historical"
    DRAFT = "Draft"
    UNKNOWN = "Unknown"


class PayerType(str, Enum):
    """Enumerated values accepted by the ``public.payer_type`` type."""

    MANAGED_CARE = "ManagedCare"
    MEDICAID = "Medicaid"
    MEDICARE_A = "MedicareA"
    MEDICARE_B = "MedicareB"
    MEDICARE_D = "MedicareD"
    OTHER = "Other"
    OUTPATIENT = "Outpatient"
    PRIVATE = "Private"
    UNKNOWN = "Unknown"


class _EHRLinkedRecord(SQLInsertModel):
    """Base class enforcing shared EHR linkage validations."""

    patient_id: UUID = Field(description="Identifier referencing public.patient")
    ehr_instance_id: UUID | None = Field(
        default=None, description="Identifier referencing public.ehr_instance"
    )
    ehr_external_id: str | None = Field(
        default=None, description="External identifier from the source EHR"
    )
    ehr_connection_status: EHRConnectionStatus | None = Field(
        default=None, description="Connection status reported by the EHR"
    )

    @model_validator(mode="after")
    def _validate_ehr_linkage(self) -> "_EHRLinkedRecord":
        if (self.ehr_instance_id is None) ^ (self.ehr_external_id is None):
            raise ValueError(
                "ehr_instance_id and ehr_external_id must both be provided or omitted"
            )
        if self.ehr_connection_status is not None and (
            self.ehr_instance_id is None or self.ehr_external_id is None
        ):
            raise ValueError(
                "ehr_connection_status requires ehr_instance_id and ehr_external_id"
            )
        return self


class PatientAllergyRecord(_EHRLinkedRecord):
    """Representation of the ``public.patient_allergy`` table."""

    id: UUID = Field(default_factory=uuid4)
    allergen: str = Field(description="Name of the allergen")
    category: AllergyCategory = Field(
        default=AllergyCategory.UNKNOWN,
        description="Allergy category enum value",
    )
    clinical_status: AllergyClinicalStatus = Field(
        description="Clinical status enum value"
    )
    created_by: str | None = Field(default=None)
    created_time: datetime | None = Field(default=None)
    onset_date: date | None = Field(default=None)
    reaction_note: str | None = Field(default=None)
    reaction_type: str | None = Field(default=None)
    reaction_sub_type: str | None = Field(default=None)
    resolved_date: date | None = Field(default=None)
    rev_by: str | None = Field(default=None)
    rev_time: datetime | None = Field(default=None)
    severity: AllergySeverity = Field(
        default=AllergySeverity.UNKNOWN,
        description="Allergy severity enum value",
    )
    type: AllergyType = Field(
        default=AllergyType.UNKNOWN, description="Allergy type enum value"
    )
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class PatientConditionRecord(_EHRLinkedRecord):
    """Representation of the ``public.patient_condition`` table."""

    id: UUID = Field(default_factory=uuid4)
    classification_description: str | None = Field(default=None)
    clinical_status: ConditionClinicalStatus = Field(
        description="Condition clinical status enum value"
    )
    comments: str | None = Field(default=None)
    created_by: str | None = Field(default=None)
    created_time: datetime | None = Field(default=None)
    icd_10_code: str | None = Field(default=None)
    icd_10_description: str | None = Field(default=None)
    onset_date: date | None = Field(default=None)
    is_primary_diagnosis: bool = Field(
        description="Indicates the primary diagnosis flag"
    )
    resolved_date: date | None = Field(default=None)
    rev_by: str | None = Field(default=None)
    rev_time: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class PatientCoverageRecord(_EHRLinkedRecord):
    """Representation of the ``public.patient_coverage`` table."""

    id: UUID = Field(default_factory=uuid4)
    payer_name: str = Field(description="Name of the payer")
    payer_type: PayerType = Field(description="Payer type enum value")
    payer_rank: int = Field(description="Rank of the coverage")
    payer_code: str | None = Field(default=None)
    payer_code_2: str | None = Field(default=None)
    informational_only: bool = Field(default=False)
    effective_time: datetime = Field(description="Coverage effective timestamp")
    expiration_time: datetime | None = Field(default=None)
    account_number: str | None = Field(default=None)
    account_description: str | None = Field(default=None)
    issuer: Dict[str, Any] | None = Field(default=None)
    insured_party: Dict[str, Any] | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class PatientMedicationRecord(_EHRLinkedRecord):
    """Representation of the ``public.patient_medication`` table."""

    id: UUID = Field(default_factory=uuid4)
    created_by: str | None = Field(default=None)
    created_time: datetime | None = Field(default=None)
    description: str = Field(default="Missing")
    directions: str = Field(default="Missing")
    discontinued_time: datetime | None = Field(default=None)
    end_time: date | None = Field(default=None)
    generic_name: str | None = Field(default=None)
    narcotic: bool | None = Field(default=None)
    order_time: datetime | None = Field(default=None)
    physician_details: Dict[str, Any] | None = Field(default=None)
    rev_by: str | None = Field(default=None)
    rev_time: datetime | None = Field(default=None)
    rx_norm_id: str | None = Field(default=None)
    start_time: date | None = Field(default=None)
    status: MedicationStatus = Field(description="Medication status enum value")
    strength: str | None = Field(default=None)
    strength_unit: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class PatientObservationRecord(_EHRLinkedRecord):
    """Representation of the ``public.patient_observation`` table."""

    id: UUID = Field(default_factory=uuid4)
    method: str | None = Field(default=None)
    recorded_by: str | None = Field(default=None)
    recorded_time: datetime | None = Field(default=None)
    data: Dict[str, Any] = Field(description="Observation payload as JSON")
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


__all__ = [
    "AllergyCategory",
    "AllergyClinicalStatus",
    "AllergySeverity",
    "AllergyType",
    "ConditionClinicalStatus",
    "MedicationStatus",
    "PayerType",
    "PatientAllergyRecord",
    "PatientConditionRecord",
    "PatientCoverageRecord",
    "PatientMedicationRecord",
    "PatientObservationRecord",
]
