"""Unit tests covering anonymisation behaviour within the patient pipeline."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

pytest.importorskip("pydantic")

from services.anonymizer.app.anonymization.replacement import ReplacementContext
from services.anonymizer.app.models import PipelinePatientRecord
from services.anonymizer.app.pipelines.patient_pipeline import (
    FieldRule,
    PatientPipeline,
    PipelineContext,
    PatientPayloadValidationError,
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

    field_rules = (
        FieldRule(("demographics", "first_name"), "PERSON"),
        FieldRule(("care_team", "*", "name"), "PERSON"),
        FieldRule(("encounters", "*", "location"), "FACILITY_NAME"),
    )

    pipeline = PatientPipeline(
        firestore_client=MagicMock(),
        repository=MagicMock(),
        ddl_key="patients",
        column_mapping={"document_id": "document_id"},
        field_rules=field_rules,
        replacement_context_factory=lambda: ReplacementContext(salt="unit-test"),
    )

    # Attach the captured calls so tests can make assertions.
    pipeline._replacement_calls = calls  # type: ignore[attr-defined]
    return pipeline


@pytest.fixture()
def patient_payload() -> dict[str, Any]:
    record = PipelinePatientRecord.model_validate(
        {
            "demographics": {"first_name": "Jane"},
            "care_team": [
                {"name": "Dr. Adams"},
                {"name": "Dr. Baker", "organization": "Downtown Clinic"},
            ],
            "encounters": [
                {"location": "St. Mary Medical Center"},
            ],
        }
    )
    return record.model_dump(mode="json", by_alias=False, exclude_none=True)


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
    assert anonymized["demographics"]["first_name"].startswith("PERSON|")
    assert anonymized["care_team"][0]["name"].startswith("PERSON|")
    assert anonymized["care_team"][1]["name"].startswith("PERSON|")
    assert anonymized["encounters"][0]["location"].startswith("FACILITY_NAME|")

    # The replacement context should be recorded on the pipeline context for summarisation.
    assert context.replacement_context is not None

    # Verify ``apply_replacement`` was invoked for each targeted field.
    assert pipeline._replacement_calls == [
        ("PERSON", "Jane"),
        ("PERSON", "Dr. Adams"),
        ("PERSON", "Dr. Baker"),
        ("FACILITY_NAME", "St. Mary Medical Center"),
    ]


def test_anonymize_patient_payload_ignores_missing_paths(pipeline: PatientPipeline) -> None:
    payload = {
        "demographics": {"first_name": None},
        "care_team": [],
        "encounters": [
            {"location": None},
            {},
        ],
    }

    context = PipelineContext(
        document_id="doc-002",
        firestore_document={"patient": payload},
        normalized_document={"patient": payload},
        patient_payload=payload,
    )

    anonymized = pipeline._anonymize_patient_payload(payload, context)

    # ``None`` values should remain untouched to avoid introducing strings where not desired.
    assert anonymized["demographics"]["first_name"] is None
    assert anonymized["care_team"] == []
    assert anonymized["encounters"][0]["location"] is None

    # Only the non-``None`` values should have triggered replacements.
    assert pipeline._replacement_calls == []


def test_extract_patient_payload_wraps_validation_errors(
    pipeline: PatientPipeline,
) -> None:
    invalid_payload = {
        "patient": {
            "demographics": {
                "first_name": "Ada",
                "date_of_birth": "31-02-2020",
            }
        }
    }

    with pytest.raises(PatientPayloadValidationError) as excinfo:
        pipeline._extract_patient_payload(invalid_payload)

    message = str(excinfo.value)
    assert "date_of_birth" in message
    assert "31-02-2020" not in message
    assert "Ada" not in message
