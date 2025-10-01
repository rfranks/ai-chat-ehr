"""Data model for rows written to ``public.patient`` in Postgres."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class PatientRow(BaseModel):
    """Representation of a ``public.patient`` row destined for Postgres."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID = Field(description="Identifier of the owning tenant")
    facility_id: UUID = Field(description="Identifier of the owning facility")
    ehr_instance_id: Optional[UUID] = Field(default=None)
    ehr_external_id: Optional[str] = Field(default=None)
    ehr_connection_status: Optional[str] = Field(default=None)
    ehr_last_full_manual_sync_at: Optional[datetime] = Field(default=None)
    name_first: str = Field(description="Patient given name")
    name_last: str = Field(description="Patient family name")
    dob: Optional[date] = Field(default=None)
    gender: str = Field(description="Patient gender enum value")
    ethnicity_description: Optional[str] = Field(default=None)
    legal_mailing_address: Optional[dict[str, Any]] = Field(default=None)
    photo_url: Optional[str] = Field(default=None)
    unit_description: Optional[str] = Field(default=None)
    floor_description: Optional[str] = Field(default=None)
    room_description: Optional[str] = Field(default=None)
    bed_description: Optional[str] = Field(default=None)
    status: str = Field(description="Patient status enum value")
    admission_time: Optional[datetime] = Field(default=None)
    discharge_time: Optional[datetime] = Field(default=None)
    death_time: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


__all__ = ["PatientRow"]
