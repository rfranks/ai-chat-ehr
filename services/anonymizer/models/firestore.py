"""Pydantic models representing Firestore patient documents."""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


def _to_camel(value: str) -> str:
    """Return ``value`` converted from snake_case to camelCase."""

    components = value.split("_")
    if not components:
        return value
    first, *rest = components
    return first + "".join(token.capitalize() for token in rest)


class FirestoreModel(BaseModel):
    """Base model for Firestore payloads using camelCase aliases."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        extra="ignore",
    )


class FirestoreName(FirestoreModel):
    """Patient name metadata stored in Firestore."""

    prefix: Optional[str] = Field(default=None, description="Optional name prefix")
    first: str = Field(description="Patient given name")
    middle: Optional[str] = Field(default=None, description="Patient middle name")
    last: str = Field(description="Patient family name")
    suffix: Optional[str] = Field(default=None, description="Optional name suffix")


class FirestoreAddress(FirestoreModel):
    """Postal address nested under a coverage entry."""

    address_line1: Optional[str] = Field(default=None)
    address_line2: Optional[str] = Field(default=None)
    city: Optional[str] = Field(default=None)
    state: Optional[str] = Field(default=None)
    postal_code: Optional[str] = Field(default=None)
    country: Optional[str] = Field(default=None)


class FirestoreCoverage(FirestoreModel):
    """Insurance coverage information stored alongside the patient."""

    member_id: Optional[str] = Field(default=None)
    payer_name: Optional[str] = Field(default=None)
    payer_id: Optional[str] = Field(default=None)
    relationship_to_subscriber: Optional[str] = Field(default=None)
    first_name: Optional[str] = Field(default=None)
    last_name: Optional[str] = Field(default=None)
    gender: Optional[str] = Field(default=None)
    alt_payer_name: Optional[str] = Field(default=None)
    insurance_type: Optional[str] = Field(default=None)
    payer_rank: Optional[int] = Field(default=None)
    address: Optional[FirestoreAddress] = Field(default=None)
    plan_effective_date: Optional[date] = Field(default=None)


class FirestoreEHRMetadata(FirestoreModel):
    """Metadata describing the originating EHR system."""

    provider: Optional[str] = Field(default=None)
    instance_id: Optional[str] = Field(default=None)
    patient_id: Optional[str] = Field(default=None)
    facility_id: Optional[str] = Field(default=None)


class FirestorePatientDocument(FirestoreModel):
    """Top-level structure of the Firestore patient document."""

    created_at: Optional[int] = Field(default=None)
    name: FirestoreName = Field(description="Patient name components")
    dob: Optional[date] = Field(default=None, description="Patient date of birth")
    gender: Optional[str] = Field(default=None)
    coverages: list[FirestoreCoverage] = Field(default_factory=list)
    ehr: Optional[FirestoreEHRMetadata] = Field(default=None)
    facility_id: Optional[str] = Field(default=None)
    facility_name: Optional[str] = Field(default=None)
    tenant_id: Optional[str] = Field(default=None)
    tenant_name: Optional[str] = Field(default=None)


__all__ = [
    "FirestoreAddress",
    "FirestoreCoverage",
    "FirestoreEHRMetadata",
    "FirestoreName",
    "FirestorePatientDocument",
]
