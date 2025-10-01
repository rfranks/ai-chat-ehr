"""Unit tests covering anonymisation behaviour within the patient pipeline."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

pytest.importorskip("pydantic")

from services.anonymizer.app.anonymization.replacement import ReplacementContext
from services.anonymizer.app.pipelines.patient_pipeline import (
    DEFAULT_FIELD_RULES,
    PatientPipeline,
    PipelineContext,
    PatientPayloadValidationError,
    _normalize_structure,
    _stringify_structure,
)


@pytest.fixture()
def pipeline(monkeypatch: pytest.MonkeyPatch) -> PatientPipeline:
    """Return a pipeline instance wired with deterministic replacement behaviour."""

    calls: list[tuple[str, str]] = []

    def fake_apply(entity_type: str, text: str, context: ReplacementContext) -> str:
        calls.append((entity_type, text))
        # Provide a readable replacement so assertions can inspect it easily.
        return f"{entity_type}|{text.upper()}"

    monkeypatch.setattr(
        "services.anonymizer.app.pipelines.patient_pipeline.apply_replacement",
        fake_apply,
    )

    pipeline = PatientPipeline(
        firestore_client=MagicMock(),
        repository=MagicMock(),
        ddl_key="patients",
        column_mapping={"document_id": "document_id"},
        field_rules=DEFAULT_FIELD_RULES,
        replacement_context_factory=lambda: ReplacementContext(salt="unit-test"),
    )

    # Attach the captured calls so tests can make assertions.
    pipeline._replacement_calls = calls  # type: ignore[attr-defined]
    return pipeline


@pytest.fixture()
def patient_payload() -> dict[str, Any]:
    return {
        "created_at": 1754272710463,
        "name": {"prefix": "Ms.", "first": "Nick", "last": "Alderman"},
        "dob": "1933-05-29",
        "gender": "female",
        "coverages": [
            {
                "member_id": "8D38CE46-",
                "payer_name": "INSURANCE_COMPANY_1580",
                "payer_id": "Unknown",
                "relationship_to_subscriber": "Self",
                "first_name": "Nick",
                "last_name": "Alderman",
                "gender": "female",
                "alt_payer_name": "FL MCD MNG-Sunshine State",
                "insurance_type": "medicaid",
                "payer_rank": 0,
                "address": {
                    "address_line1": "247 Reese Road",
                    "city": "Tampa",
                    "state": "FL",
                    "postal_code": "33605",
                    "country": "United States",
                },
                "plan_effective_date": "2015-04-01",
            },
            {
                "member_id": "Unknown",
                "payer_name": "Unknown",
                "payer_id": "Unknown",
                "relationship_to_subscriber": "Other",
                "first_name": "Unknown",
                "last_name": "Unknown",
                "gender": "unknown",
                "alt_payer_name": "Resident Liability",
                "insurance_type": "private",
                "payer_rank": 1,
            },
            {
                "member_id": "Unknown",
                "payer_name": "Unknown",
                "payer_id": "Unknown",
                "relationship_to_subscriber": "Other",
                "first_name": "Unknown",
                "last_name": "Unknown",
                "gender": "unknown",
                "alt_payer_name": "Medicare B",
                "insurance_type": "medicareB",
                "payer_rank": 2,
            },
            {
                "member_id": "8D38CE46-",
                "payer_name": "INSURANCE_COMPANY_1580",
                "payer_id": "Unknown",
                "relationship_to_subscriber": "Self",
                "first_name": "Nick",
                "last_name": "Alderman",
                "gender": "female",
                "alt_payer_name": "X-over Medicare B to Medicaid",
                "insurance_type": "medicaid",
                "payer_rank": 5,
                "address": {
                    "address_line1": "247 Reese Road",
                    "city": "Tampa",
                    "state": "FL",
                    "postal_code": "33605",
                    "country": "United States",
                },
                "plan_effective_date": "2015-04-01",
            },
        ],
        "ehr": {
            "provider": "PointClickCareSandbox",
            "instance_id": "92D707EA-E9F9-4B4A-95C3-A98C585A07F7",
            "patient_id": "6231",
            "facility_id": "12",
        },
        "facility_id": "6ONQmxOcSRWFGkxOHW3V",
        "facility_name": "Willow Creek Rehabilitation Center",
        "tenant_id": "Demo-SNF-di0ku",
        "tenant_name": "Demo SNF",
    }


def test_anonymize_patient_payload_applies_field_rules(
    pipeline: PatientPipeline, patient_payload: dict[str, Any]
) -> None:
    payload = patient_payload

    context = PipelineContext(
        document_id="doc-001",
        firestore_document={"patient": payload},
        normalized_document={"patient": payload},
        patient_payload=payload,
    )

    anonymized = pipeline._anonymize_patient_payload(payload, context)

    # Ensure replacements were applied to all configured paths.
    assert anonymized["name"]["first"].startswith("PERSON|")
    assert anonymized["name"]["last"].startswith("PERSON|")
    assert anonymized["dob"].startswith("DATE_TIME|")

    coverage = anonymized["coverages"][0]
    assert coverage["first_name"].startswith("PERSON|")
    assert coverage["last_name"].startswith("PERSON|")
    assert coverage["member_id"].startswith("MEDICAL_RECORD_NUMBER|")
    assert coverage["address"]["address_line1"].startswith("STREET_ADDRESS|")

    assert anonymized["ehr"]["patient_id"].startswith("MEDICAL_RECORD_NUMBER|")

    # The replacement context should be recorded on the pipeline context for summarisation.
    assert context.replacement_context is not None

    # Verify ``apply_replacement`` was invoked for each targeted field.
    assert pipeline._replacement_calls == [
        ("PERSON", "Nick"),
        ("PERSON", "Alderman"),
        ("DATE_TIME", "1933-05-29"),
        ("PERSON", "Nick"),
        ("PERSON", "Unknown"),
        ("PERSON", "Unknown"),
        ("PERSON", "Nick"),
        ("PERSON", "Alderman"),
        ("PERSON", "Unknown"),
        ("PERSON", "Unknown"),
        ("PERSON", "Alderman"),
        ("MEDICAL_RECORD_NUMBER", "8D38CE46-"),
        ("MEDICAL_RECORD_NUMBER", "Unknown"),
        ("MEDICAL_RECORD_NUMBER", "Unknown"),
        ("MEDICAL_RECORD_NUMBER", "8D38CE46-"),
        ("STREET_ADDRESS", "247 Reese Road"),
        ("STREET_ADDRESS", "247 Reese Road"),
        ("MEDICAL_RECORD_NUMBER", "6231"),
    ]


def test_anonymize_patient_payload_ignores_missing_paths(pipeline: PatientPipeline) -> None:
    payload = {
        "name": {"first": None, "last": None},
        "coverages": [
            {
                "member_id": None,
                "first_name": None,
                "last_name": None,
                "address": {"address_line1": None},
            }
        ],
        "ehr": {"patient_id": None},
    }

    context = PipelineContext(
        document_id="doc-002",
        firestore_document={"patient": payload},
        normalized_document={"patient": payload},
        patient_payload=payload,
    )

    anonymized = pipeline._anonymize_patient_payload(payload, context)

    # ``None`` values should remain untouched to avoid introducing strings where not desired.
    assert anonymized["name"]["first"] is None

    # Only the non-``None`` values should have triggered replacements.
    assert pipeline._replacement_calls == []


def test_extract_patient_payload_wraps_validation_errors(
    pipeline: PatientPipeline,
) -> None:
    invalid_payload = {
        "patient": {
            "name": {"first": "Ada"},
            "dob": "31-02-2020",
        }
    }

    with pytest.raises(PatientPayloadValidationError) as excinfo:
        pipeline._extract_patient_payload(invalid_payload)

    message = str(excinfo.value)
    assert "dob" in message
    assert "31-02-2020" not in message
    assert "Ada" not in message


def test_normalize_structure_strips_unmapped_fields() -> None:
    firestore_payload = {
        "patient": {
            "createdAt": 1754272710463,
            "name": {
                "first": "Nick",
                "last": "Alderman",
                "preferredName": "Nicky",
            },
            "dob": "1933-05-29",
            "coverages": [
                {
                    "memberId": "8D38CE46-",
                    "firstName": "Nick",
                    "lastName": "Alderman",
                    "address": {
                        "addressLine1": "247 Reese Road",
                        "geoCode": "remove",
                    },
                    "extra": True,
                }
            ],
            "ehr": {
                "patientId": "6231",
                "facilityId": "12",
                "redundant": "drop",
            },
            "legacyField": "should vanish",
        },
        "normalized": {
            "tenantId": "tenant-123",
            "facilityId": "facility-9",
            "residentId": "forbidden",
            "legalMailingAddress": {
                "line1": "123 Main St",
                "geoCode": "remove",
            },
        },
        "metadata": {"keep": "root extras are fine"},
    }

    normalized = _normalize_structure(firestore_payload)

    patient = normalized["patient"]
    assert patient["created_at"] == 1754272710463
    assert patient["name"] == {"first": "Nick", "last": "Alderman"}
    assert patient["dob"] == "1933-05-29"

    coverage = patient["coverages"][0]
    assert coverage == {
        "member_id": "8D38CE46-",
        "first_name": "Nick",
        "last_name": "Alderman",
        "address": {"address_line1": "247 Reese Road"},
    }

    ehr = patient["ehr"]
    assert ehr == {"patient_id": "6231", "facility_id": "12"}

    assert "legacy_field" not in patient

    normalized_meta = normalized["normalized"]
    assert normalized_meta == {
        "tenant_id": "tenant-123",
        "facility_id": "facility-9",
        "legal_mailing_address": {"line1": "123 Main St"},
    }

    # Ensure unrelated root keys remain untouched for context/debugging purposes.
    assert normalized["metadata"] == {"keep": "root extras are fine"}


def test_stringify_structure_masks_unknown_fields() -> None:
    structure = {
        "patient": {
            "name": {"first": b"ada", "unused": "drop"},
            "coverages": [
                {
                    "first_name": b"nick",
                    "address": {"address_line1": b"247 Reese Road", "ignore": True},
                }
            ],
        },
        "normalized": {
            "tenant_id": "tenant-321",
            "forbidden": "discard",
        },
        "raw": {"any": "thing"},
    }

    stringified = _stringify_structure(structure)

    assert stringified["patient"]["name"] == {"first": "ada"}
    assert stringified["patient"]["coverages"] == [
        {"first_name": "nick", "address": {"address_line1": "247 Reese Road"}}
    ]
    assert stringified["normalized"] == {"tenant_id": "tenant-321"}
    assert stringified["raw"] == {"any": "thing"}
