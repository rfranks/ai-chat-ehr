from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from uuid import uuid4
import sys

import pytest
from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.generator.models import (
    Gender,
    PatientRecord,
    PatientSeed,
    PatientStatus,
)


def _build_seed(include_ehr: bool = True) -> PatientSeed:
    facility_id = uuid4()
    if include_ehr:
        return PatientSeed(
            facility_id=facility_id,
            ehr_instance_id=uuid4(),
            ehr_external_id="external-123",
        )
    return PatientSeed(facility_id=facility_id)


def test_patient_record_serializes_sql_parameters() -> None:
    patient = PatientRecord(
        tenant_id=uuid4(),
        seed=_build_seed(),
        name_first="Alice",
        name_last="Smith",
        gender=Gender.FEMALE,
        status=PatientStatus.ACTIVE,
        dob=date(1990, 1, 1),
        admission_time=datetime(2024, 1, 1, 9, 30, 0),
    )

    params = patient.as_parameters()

    assert params["tenant_id"] == patient.tenant_id
    assert params["facility_id"] == patient.facility_id
    assert params["ehr_instance_id"] == patient.ehr_instance_id
    assert params["ehr_external_id"] == patient.ehr_external_id
    assert params["gender"] == Gender.FEMALE.value
    assert params["status"] == PatientStatus.ACTIVE.value
    assert "seed" not in params


def test_patient_record_sql_parameters_respects_primary_key_flag() -> None:
    patient = PatientRecord(
        tenant_id=uuid4(),
        seed=_build_seed(include_ehr=False),
        name_first="Bob",
        name_last="Jones",
        gender=Gender.MALE,
        status=PatientStatus.PENDING,
    )

    params = patient.as_parameters(include_primary_key=False)

    assert "id" not in params
    assert params["facility_id"] == patient.facility_id
    assert "ehr_instance_id" not in params
    assert "ehr_external_id" not in params


def test_uniqueness_seed_matches_seed_values() -> None:
    patient = PatientRecord(
        tenant_id=uuid4(),
        seed=_build_seed(),
        name_first="Dana",
        name_last="Lee",
        gender=Gender.UNKNOWN,
        status=PatientStatus.DISCHARGED,
    )

    assert patient.uniqueness_seed() == (
        patient.facility_id,
        patient.ehr_instance_id,
        patient.ehr_external_id,
    )


def test_patient_seed_requires_matching_ehr_identifiers() -> None:
    with pytest.raises(ValidationError):
        PatientSeed(facility_id=uuid4(), ehr_instance_id=uuid4())

    with pytest.raises(ValidationError):
        PatientSeed(facility_id=uuid4(), ehr_external_id="abc")


@pytest.mark.parametrize(
    "field, value",
    [
        ("gender", "invalid"),
        ("status", "not-a-status"),
    ],
)
def test_patient_record_enforces_enum_values(field: str, value: str) -> None:
    data = {
        "tenant_id": uuid4(),
        "seed": _build_seed(),
        "name_first": "Casey",
        "name_last": "Taylor",
        "gender": Gender.UNKNOWN,
        "status": PatientStatus.UNKNOWN,
    }
    data[field] = value

    with pytest.raises(ValidationError):
        PatientRecord(**data)
