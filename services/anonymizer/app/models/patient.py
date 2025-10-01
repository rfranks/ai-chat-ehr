"""Pydantic models describing Firestore patient documents."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field

from shared.models import PatientRecord

__all__ = [
    "FirestoreMailingAddress",
    "FirestoreNormalizedPatient",
    "FirestorePatientDocumentData",
    "FirestorePatientDocumentSnapshot",
]


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

    patient: PatientRecord | None = Field(default=None, alias="patient")
    record: PatientRecord | None = Field(default=None, alias="record")
    normalized: FirestoreNormalizedPatient | None = Field(
        default=None, alias="normalized"
    )
    metadata: Mapping[str, Any] | None = Field(default=None, alias="metadata")
    raw: Mapping[str, Any] | None = Field(default=None, alias="raw")

    def patient_payload(self) -> PatientRecord | None:
        """Return the patient record embedded in the Firestore document."""

        if self.patient is not None:
            return self.patient
        return self.record


class FirestorePatientDocumentSnapshot(BaseModel):
    """Typed view over Firestore snapshots returned by the client wrapper."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    document_id: str = Field(alias="documentId")
    data: FirestorePatientDocumentData
