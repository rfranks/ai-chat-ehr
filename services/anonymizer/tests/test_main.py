from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi import HTTPException

from services.anonymizer.app.main import create_app
from services.anonymizer.app.pipelines.patient_pipeline import (
    PatientDocumentNotFoundError,
    PipelineRunSummary,
    ReplacementSummary,
)
from services.anonymizer.app.config import get_settings


def _get_anonymize_endpoint(app):
    for route in app.routes:
        if getattr(route, "path", None) == "/anonymize/patients/{document_id}":
            return route.endpoint
    raise AssertionError("Anonymize route not registered")


@pytest.mark.anyio
async def test_anonymize_patient_returns_summary() -> None:
    app = create_app()
    handler = _get_anonymize_endpoint(app)

    summary = PipelineRunSummary(
        document_id="doc-123",
        collection="patients",
        anonymized_patient={"foo": "bar"},
        replacements=(ReplacementSummary(entity_type="PERSON", count=2),),
        repository_results=({"id": 1},),
    )

    class StubPipeline:
        async def run_with_summary(self, document_id: str, *, collection: str | None = None) -> PipelineRunSummary:  # noqa: D401 - simple stub
            assert document_id == "doc-123"
            assert collection == "patients"
            return summary

    result = await handler(
        document_id="doc-123",
        pipeline=StubPipeline(),
        settings=get_settings(),
    )

    payload = result
    assert payload["documentId"] == "doc-123"
    assert payload["collection"] == "patients"
    assert payload["anonymizedPatient"] == {"foo": "bar"}
    assert payload["anonymization"] == {
        "totalReplacements": 2,
        "entities": [{"entityType": "PERSON", "count": 2}],
    }
    assert payload["repository"] == {
        "rows": [{"id": 1}],
        "count": 1,
    }


@pytest.mark.anyio
async def test_anonymize_patient_handles_missing_document() -> None:
    app = create_app()
    handler = _get_anonymize_endpoint(app)

    class MissingPipeline:
        async def run_with_summary(self, document_id: str, *, collection: str | None = None) -> PipelineRunSummary:  # noqa: D401 - simple stub
            raise PatientDocumentNotFoundError(document_id)

    with pytest.raises(HTTPException) as excinfo:
        await handler(
            document_id="unknown",
            pipeline=MissingPipeline(),
            settings=get_settings(),
        )

    error = excinfo.value
    assert error.status_code == 404
    assert error.detail == {
        "message": "Patient document 'unknown' was not found in Firestore.",
        "documentId": "unknown",
    }


@pytest.mark.anyio
async def test_anonymize_patient_handles_unexpected_error() -> None:
    app = create_app()
    handler = _get_anonymize_endpoint(app)

    class FailingPipeline:
        async def run_with_summary(self, document_id: str, *, collection: str | None = None) -> PipelineRunSummary:  # noqa: D401 - simple stub
            raise RuntimeError("boom")

    with pytest.raises(HTTPException) as excinfo:
        await handler(
            document_id="doc-123",
            pipeline=FailingPipeline(),
            settings=get_settings(),
        )

    error = excinfo.value
    assert error.status_code == 500
    assert error.detail == "Failed to anonymize patient document."
