"""Pydantic models describing Firestore patient documents."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "FirestoreCoverageAddress",
    "FirestoreCoverage",
    "FirestoreEHRMetadata",
    "FirestoreName",
    "FirestoreNormalizedPatient",
    "FirestorePatientDocumentData",
    "FirestorePatientDocumentSnapshot",
    "PipelinePatientRecord",
]


class FirestoreName(BaseModel):
    """Structured patient name information captured in Firestore."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    prefix: str | None = Field(default=None, alias="prefix")
    first: str | None = Field(default=None, alias="first")
    middle: str | None = Field(default=None, alias="middle")
    last: str | None = Field(default=None, alias="last")
    suffix: str | None = Field(default=None, alias="suffix")


class FirestoreCoverageAddress(BaseModel):
    """Mailing address nested beneath insurance coverage entries."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    address_line1: str | None = Field(default=None, alias="addressLine1")
    address_line2: str | None = Field(default=None, alias="addressLine2")
    city: str | None = Field(default=None, alias="city")
    state: str | None = Field(default=None, alias="state")
    postal_code: str | None = Field(default=None, alias="postalCode")
    country: str | None = Field(default=None, alias="country")


class FirestoreCoverage(BaseModel):
    """Insurance coverage metadata stored on the patient document."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    member_id: str | None = Field(default=None, alias="memberId")
    payer_name: str | None = Field(default=None, alias="payerName")
    payer_id: str | None = Field(default=None, alias="payerId")
    relationship_to_subscriber: str | None = Field(
        default=None, alias="relationshipToSubscriber"
    )
    first_name: str | None = Field(default=None, alias="firstName")
    last_name: str | None = Field(default=None, alias="lastName")
    gender: str | None = Field(default=None, alias="gender")
    alt_payer_name: str | None = Field(default=None, alias="altPayerName")
    insurance_type: str | None = Field(default=None, alias="insuranceType")
    payer_rank: int | None = Field(default=None, alias="payerRank")
    address: FirestoreCoverageAddress | None = Field(default=None, alias="address")
    plan_effective_date: date | None = Field(default=None, alias="planEffectiveDate")


class FirestoreEHRMetadata(BaseModel):
    """Identifiers linking the Firestore patient to its source EHR."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    provider: str | None = Field(default=None, alias="provider")
    instance_id: str | None = Field(default=None, alias="instanceId")
    patient_id: str | None = Field(default=None, alias="patientId")
    facility_id: str | None = Field(default=None, alias="facilityId")


class FirestoreMailingAddress(BaseModel):
    """Structured representation of a patient's mailing address."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    line1: str | None = Field(default=None, alias="line1")
    line2: str | None = Field(default=None, alias="line2")
    city: str | None = Field(default=None, alias="city")
    state: str | None = Field(default=None, alias="state")
    postal_code: str | None = Field(default=None, alias="postalCode")


class FirestoreNormalizedPatient(BaseModel):
    """Normalized metadata extracted from Firestore documents."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    tenant_id: str | None = Field(default=None, alias="tenantId")
    facility_id: str | None = Field(default=None, alias="facilityId")
    ehr_instance_id: str | None = Field(default=None, alias="ehrInstanceId")
    ehr_external_id: str | None = Field(default=None, alias="ehrExternalId")
    ehr_connection_status: str | None = Field(
        default=None, alias="ehrConnectionStatus"
    )
    ehr_last_full_manual_sync_at: datetime | str | None = Field(
        default=None, alias="ehrLastFullManualSyncAt"
    )
    legal_mailing_address: FirestoreMailingAddress | None = Field(
        default=None, alias="legalMailingAddress"
    )
    photo_url: str | None = Field(default=None, alias="photoUrl")
    unit_description: str | None = Field(default=None, alias="unitDescription")
    floor_description: str | None = Field(default=None, alias="floorDescription")
    room_description: str | None = Field(default=None, alias="roomDescription")
    bed_description: str | None = Field(default=None, alias="bedDescription")
    status: str | None = Field(default=None, alias="status")
    admission_time: datetime | str | None = Field(default=None, alias="admissionTime")
    discharge_time: datetime | str | None = Field(default=None, alias="dischargeTime")
    death_time: datetime | str | None = Field(default=None, alias="deathTime")


class FirestorePatientDocumentData(BaseModel):
    """Payload stored under a Firestore patient document."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    patient: "PipelinePatientRecord" | None = Field(default=None, alias="patient")
    record: "PipelinePatientRecord" | None = Field(default=None, alias="record")
    normalized: FirestoreNormalizedPatient | None = Field(
        default=None, alias="normalized"
    )
    metadata: Mapping[str, Any] | None = Field(default=None, alias="metadata")
    raw: Mapping[str, Any] | None = Field(default=None, alias="raw")

    def patient_payload(self) -> "PipelinePatientRecord" | None:
        """Return the patient record embedded in the Firestore document."""

        if self.patient is not None:
            return self.patient
        return self.record


class FirestorePatientDocumentSnapshot(BaseModel):
    """Typed view over Firestore snapshots returned by the client wrapper."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    document_id: str = Field(alias="documentId")
    data: FirestorePatientDocumentData


class PipelinePatientRecord(BaseModel):
    """Patient payload schema tailored for the anonymizer pipeline."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    created_at: int | datetime | None = Field(default=None, alias="createdAt")
    name: FirestoreName | None = Field(default=None, alias="name")
    dob: date | None = Field(default=None, alias="dob")
    gender: str | None = Field(default=None, alias="gender")
    coverages: list[FirestoreCoverage] = Field(default_factory=list, alias="coverages")
    ehr: FirestoreEHRMetadata | None = Field(default=None, alias="ehr")
    facility_id: str | None = Field(default=None, alias="facilityId")
    facility_name: str | None = Field(default=None, alias="facilityName")
    tenant_id: str | None = Field(default=None, alias="tenantId")
    tenant_name: str | None = Field(default=None, alias="tenantName")
