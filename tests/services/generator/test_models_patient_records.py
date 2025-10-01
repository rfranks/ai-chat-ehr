import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.generator.models import (
    AllergyCategory,
    AllergyClinicalStatus,
    AllergySeverity,
    AllergyType,
    EHRConnectionStatus,
    MedicationStatus,
    PatientAllergyRecord,
    PatientCoverageRecord,
    PatientMedicationRecord,
    PayerType,
)


def _ehr_kwargs() -> dict:
    return {
        "ehr_instance_id": uuid4(),
        "ehr_external_id": "ehr-123",
        "ehr_connection_status": EHRConnectionStatus.CONNECTED,
    }


def test_ehr_linkage_requires_matching_identifiers() -> None:
    base = {
        "patient_id": uuid4(),
        "allergen": "Peanuts",
        "clinical_status": AllergyClinicalStatus.ACTIVE,
    }

    with pytest.raises(ValidationError):
        PatientAllergyRecord(**base, ehr_instance_id=uuid4())

    with pytest.raises(ValidationError):
        PatientAllergyRecord(**base, ehr_external_id="abc")

    with pytest.raises(ValidationError):
        PatientAllergyRecord(
            **base,
            ehr_connection_status=EHRConnectionStatus.CONNECTED,
        )


def test_patient_allergy_serializes_parameters() -> None:
    allergy = PatientAllergyRecord(
        patient_id=uuid4(),
        allergen="Peanuts",
        clinical_status=AllergyClinicalStatus.ACTIVE,
        category=AllergyCategory.FOOD,
        severity=AllergySeverity.SEVERE,
        type=AllergyType.ALLERGY,
        onset_date=datetime(2023, 1, 1, 12, 0, 0).date(),
        **_ehr_kwargs(),
    )

    params = allergy.as_parameters(include_primary_key=False)

    assert "id" not in params
    assert params["allergen"] == "Peanuts"
    assert params["category"] == AllergyCategory.FOOD.value
    assert params["severity"] == AllergySeverity.SEVERE.value
    assert params["type"] == AllergyType.ALLERGY.value
    assert params["ehr_connection_status"] == EHRConnectionStatus.CONNECTED.value


def test_patient_medication_defaults_and_serialization() -> None:
    medication = PatientMedicationRecord(
        patient_id=uuid4(),
        status=MedicationStatus.ACTIVE,
        **_ehr_kwargs(),
    )

    params = medication.as_parameters()

    assert params["description"] == "Missing"
    assert params["directions"] == "Missing"
    assert params["status"] == MedicationStatus.ACTIVE.value


def test_patient_coverage_requires_effective_time() -> None:
    with pytest.raises(ValidationError):
        PatientCoverageRecord(
            patient_id=uuid4(),
            payer_name="InsureCo",
            payer_type=PayerType.PRIVATE,
            payer_rank=1,
            **_ehr_kwargs(),
        )


def test_patient_coverage_serializes_json_fields() -> None:
    coverage = PatientCoverageRecord(
        patient_id=uuid4(),
        payer_name="InsureCo",
        payer_type=PayerType.PRIVATE,
        payer_rank=1,
        effective_time=datetime(2024, 1, 1, 0, 0, 0),
        issuer={"name": "InsureCo"},
        insured_party={"name": "John Doe"},
        **_ehr_kwargs(),
    )

    params = coverage.as_parameters(include_primary_key=False)

    assert "id" not in params
    assert params["issuer"] == {"name": "InsureCo"}
    assert params["insured_party"] == {"name": "John Doe"}
    assert params["payer_type"] == PayerType.PRIVATE.value
