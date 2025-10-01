"""Patient models for the generator service."""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import Enum
from typing import Any, Dict, Iterator, Tuple
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _utcnow() -> datetime:
    """Return a naive UTC timestamp compatible with ``timestamp`` columns."""

    return datetime.now(UTC).replace(tzinfo=None)


class Gender(str, Enum):
    """Enumerated values accepted by the ``public.gender`` type."""

    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"


class PatientStatus(str, Enum):
    """Enumerated values accepted by the ``public.patient_status`` type."""

    ACTIVE = "Active"
    DISCHARGED = "Discharged"
    PENDING = "Pending"
    UNKNOWN = "Unknown"


class PatientSeed(BaseModel):
    """Subset of fields participating in patient uniqueness constraints."""

    model_config = ConfigDict(populate_by_name=True, frozen=True)

    facility_id: UUID = Field(description="Identifier of the owning facility")
    ehr_instance_id: UUID | None = Field(
        default=None, description="Identifier of the source EHR instance"
    )
    ehr_external_id: str | None = Field(
        default=None, description="Source system identifier for the patient"
    )

    @model_validator(mode="after")
    def validate_uniqueness(self) -> "PatientSeed":
        """Ensure the seed fields are either fully populated or omitted."""

        if (self.ehr_instance_id is None) ^ (self.ehr_external_id is None):
            raise ValueError(
                "ehr_instance_id and ehr_external_id must both be provided or omitted"
            )
        return self

    def as_tuple(self) -> Tuple[UUID, UUID | None, str | None]:
        """Return a tuple suitable for deterministic hashing."""

        return (self.facility_id, self.ehr_instance_id, self.ehr_external_id)


class PatientRecord(BaseModel):
    """Representation of the patient columns required by the generator."""

    model_config = ConfigDict(populate_by_name=True, validate_assignment=True)

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID = Field(description="Identifier of the owning tenant")
    seed: PatientSeed = Field(description="Seed fields enforcing uniqueness constraints")
    name_first: str = Field(description="Patient given name")
    name_last: str = Field(description="Patient family name")
    gender: Gender = Field(description="Patient gender enum value")
    status: PatientStatus = Field(description="Patient status enum value")
    ehr_connection_status: str | None = Field(default=None)
    ehr_last_full_manual_sync_at: datetime | None = Field(default=None)
    dob: date | None = Field(default=None)
    ethnicity_description: str | None = Field(default=None)
    legal_mailing_address: Dict[str, Any] | None = Field(default=None)
    photo_url: str | None = Field(default=None)
    unit_description: str | None = Field(default=None)
    floor_description: str | None = Field(default=None)
    room_description: str | None = Field(default=None)
    bed_description: str | None = Field(default=None)
    admission_time: datetime | None = Field(default=None)
    discharge_time: datetime | None = Field(default=None)
    death_time: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @property
    def facility_id(self) -> UUID:
        """Proxy to the facility identifier within :class:`PatientSeed`."""

        return self.seed.facility_id

    @property
    def ehr_instance_id(self) -> UUID | None:
        """Proxy to the optional EHR instance identifier."""

        return self.seed.ehr_instance_id

    @property
    def ehr_external_id(self) -> str | None:
        """Proxy to the optional EHR external identifier."""

        return self.seed.ehr_external_id

    def uniqueness_seed(self) -> Tuple[UUID, UUID | None, str | None]:
        """Return the tuple that participates in the database unique index."""

        return self.seed.as_tuple()

    def sql_parameter_items(
        self, *, include_primary_key: bool = True
    ) -> Iterator[Tuple[str, Any]]:
        """Iterate over non-null column/value pairs for SQL operations."""

        column_map: Dict[str, Any] = self.model_dump(exclude={"seed"})
        column_map.update(
            {
                "facility_id": self.facility_id,
                "ehr_instance_id": self.ehr_instance_id,
                "ehr_external_id": self.ehr_external_id,
            }
        )

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
        """Alias for :meth:`as_sql_parameters` to provide a common interface."""

        return self.as_sql_parameters(include_primary_key=include_primary_key)


__all__ = [
    "Gender",
    "PatientStatus",
    "PatientSeed",
    "PatientRecord",
]
