"""Generator-facing models for patient-related clinical data."""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import Enum
from typing import Any, Dict, Iterator
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    """Return a naive UTC timestamp compatible with ``timestamp`` columns."""

    return datetime.now(UTC).replace(tzinfo=None)


class SqlParameterMixin(BaseModel):
    """Mixin providing helpers for preparing SQL parameter mappings."""

    model_config = ConfigDict(populate_by_name=True, validate_assignment=True)

    def sql_parameter_items(
        self, *, include_primary_key: bool = True
    ) -> Iterator[tuple[str, Any]]:
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

    def as_parameters(self, *, include_primary_key: bool = True) -> Dict[str, Any]:
        """Alias matching the patient model helper for consistency."""

        return self.as_sql_parameters(include_primary_key=include_primary_key)


class EhrConnectionStatus(str, Enum):
    """Enumerated values accepted by the ``public.ehr_connection_status`` type."""

    CONNECTED = "Connected"
    DISCONNECTED = "Disconnected"


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


class PatientAllergyRecord(SqlParameterMixin):
    """Representation of the ``public.patient_allergy`` table."""

    id: UUID = Field(default_factory=uuid4)
    patient_id: UUID = Field(description="Identifier of the owning patient")
    ehr_instance_id: UUID | None = Field(
        default=None, description="Identifier of the source EHR instance"
    )
    ehr_external_id: str | None = Field(
        default=None, description="Source system identifier for the allergy"
    )
    ehr_connection_status: EhrConnectionStatus | None = Field(default=None)
    allergen: str = Field(description="Allergen description recorded in the EHR")
    category: AllergyCategory = Field(
        default=AllergyCategory.UNKNOWN,
        description="Categorization of the allergen",
    )
    clinical_status: AllergyClinicalStatus = Field(
        description="Lifecycle status for the allergy record"
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
        description="Documented severity of the reaction",
    )
    allergy_type: AllergyType = Field(
        default=AllergyType.UNKNOWN,
        alias="type",
        serialization_alias="type",
        description="Classification of the allergy record",
    )
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class PatientConditionRecord(SqlParameterMixin):
    """Representation of the ``public.patient_condition`` table."""

    id: UUID = Field(default_factory=uuid4)
    patient_id: UUID = Field(description="Identifier of the owning patient")
    ehr_instance_id: UUID | None = Field(default=None)
    ehr_external_id: str | None = Field(default=None)
    ehr_connection_status: EhrConnectionStatus | None = Field(default=None)
    classification_description: str | None = Field(default=None)
    clinical_status: ConditionClinicalStatus = Field(
        description="Lifecycle status for the condition"
    )
    comments: str | None = Field(default=None)
    created_by: str | None = Field(default=None)
    created_time: datetime | None = Field(default=None)
    icd_10_code: str | None = Field(default=None)
    icd_10_description: str | None = Field(default=None)
    onset_date: date | None = Field(default=None)
    is_primary_diagnosis: bool = Field(
        description="Flag indicating whether the diagnosis is primary"
    )
    resolved_date: date | None = Field(default=None)
    rev_by: str | None = Field(default=None)
    rev_time: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class PatientCoverageRecord(SqlParameterMixin):
    """Representation of the ``public.patient_coverage`` table."""

    id: UUID = Field(default_factory=uuid4)
    patient_id: UUID = Field(description="Identifier of the covered patient")
    ehr_instance_id: UUID | None = Field(default=None)
    ehr_external_id: str | None = Field(default=None)
    ehr_connection_status: EhrConnectionStatus | None = Field(default=None)
    payer_name: str = Field(description="Name of the payer organization")
    payer_type: PayerType = Field(alias="payer_type")
    payer_rank: int = Field(description="Rank applied to ordering multiple coverages")
    payer_code: str | None = Field(default=None)
    payer_code_2: str | None = Field(default=None)
    informational_only: bool = Field(default=False)
    effective_time: datetime = Field(
        description="Timestamp when the coverage becomes effective"
    )
    expiration_time: datetime | None = Field(default=None)
    account_number: str | None = Field(default=None)
    account_description: str | None = Field(default=None)
    issuer: Dict[str, Any] | list[Any] | None = Field(default=None)
    insured_party: Dict[str, Any] | list[Any] | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class PatientMedicationRecord(SqlParameterMixin):
    """Representation of the ``public.patient_medication`` table."""

    id: UUID = Field(default_factory=uuid4)
    patient_id: UUID = Field(description="Identifier of the patient receiving medication")
    ehr_instance_id: UUID | None = Field(default=None)
    ehr_external_id: str | None = Field(default=None)
    ehr_connection_status: EhrConnectionStatus | None = Field(default=None)
    created_by: str | None = Field(default=None)
    created_time: datetime | None = Field(default=None)
    description: str = Field(default="Missing")
    directions: str = Field(default="Missing")
    discontinued_time: datetime | None = Field(default=None)
    end_time: date | None = Field(default=None)
    generic_name: str | None = Field(default=None)
    narcotic: bool | None = Field(default=None)
    order_time: datetime | None = Field(default=None)
    physician_details: Dict[str, Any] | list[Any] | None = Field(default=None)
    rev_by: str | None = Field(default=None)
    rev_time: datetime | None = Field(default=None)
    rx_norm_id: str | None = Field(default=None)
    start_time: date | None = Field(default=None)
    status: MedicationStatus = Field(description="Lifecycle status for the medication")
    strength: str | None = Field(default=None)
    strength_unit: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class PatientObservationRecord(SqlParameterMixin):
    """Representation of the ``public.patient_observation`` table."""

    id: UUID = Field(default_factory=uuid4)
    patient_id: UUID = Field(description="Identifier of the patient observed")
    ehr_instance_id: UUID | None = Field(default=None)
    ehr_external_id: str | None = Field(default=None)
    ehr_connection_status: EhrConnectionStatus | None = Field(default=None)
    method: str | None = Field(default=None)
    recorded_by: str | None = Field(default=None)
    recorded_time: datetime | None = Field(default=None)
    data: Dict[str, Any] | list[Any] = Field(
        description="Structured observation payload from the EHR"
    )
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


__all__ = [
    "SqlParameterMixin",
    "EhrConnectionStatus",
    "AllergyCategory",
    "AllergyClinicalStatus",
    "AllergySeverity",
    "AllergyType",
    "ConditionClinicalStatus",
    "PayerType",
    "MedicationStatus",
    "PatientAllergyRecord",
    "PatientConditionRecord",
    "PatientCoverageRecord",
    "PatientMedicationRecord",
    "PatientObservationRecord",
]

