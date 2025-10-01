"""Tests covering resilience behaviour in the patient pipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("pydantic")

from services.anonymizer.app.clients.firestore_client import FirestorePatientDocument
from services.anonymizer.app.models import PipelinePatientRecord
from services.anonymizer.app.pipelines.patient_pipeline import PatientPipeline
from services.anonymizer.app.pipelines.resilience import RetryPolicy


def _build_minimal_patient_document(document_id: str) -> FirestorePatientDocument:
    payload = PipelinePatientRecord.model_validate({}).model_dump(
        mode="json", by_alias=False, exclude_none=True
    )
    return FirestorePatientDocument(document_id=document_id, data={"patient": payload})


@pytest.mark.asyncio
async def test_patient_pipeline_retries_firestore_calls() -> None:
    firestore = MagicMock()
    firestore.get_patient_document.side_effect = [
        RuntimeError("transient firestore error"),
        _build_minimal_patient_document("doc-123"),
    ]

    repository = AsyncMock()
    repository.insert.return_value = [{"document_id": "doc-123"}]

    pipeline = PatientPipeline(
        firestore_client=firestore,
        repository=repository,
        ddl_key="patients",
        column_mapping={"document_id": "document_id"},
        retry_policy=RetryPolicy(
            attempts=2,
            initial_delay=0.0,
            max_delay=0.0,
            backoff_multiplier=1.0,
        ),
    )

    summary = await pipeline.run_with_summary("doc-123")

    assert summary.document_id == "doc-123"
    assert firestore.get_patient_document.call_count == 2
    repository.insert.assert_awaited_once()


@pytest.mark.asyncio
async def test_patient_pipeline_gracefully_degrades_on_repository_failure() -> None:
    firestore = MagicMock()
    firestore.get_patient_document.return_value = _build_minimal_patient_document(
        "doc-456"
    )

    repository = AsyncMock()
    repository.insert.side_effect = RuntimeError("database unavailable")

    policy = RetryPolicy(
        attempts=3,
        initial_delay=0.0,
        max_delay=0.0,
        backoff_multiplier=1.0,
    )

    pipeline = PatientPipeline(
        firestore_client=firestore,
        repository=repository,
        ddl_key="patients",
        column_mapping={"document_id": "document_id"},
        retry_policy=policy,
    )

    summary = await pipeline.run_with_summary("doc-456")

    assert summary.repository_results == ()
    assert summary.persistence_error is not None
    assert summary.persistence_succeeded is False
    assert repository.insert.await_count == policy.attempts
    # ``run`` should mirror ``run_with_summary`` and surface graceful degradation.
    assert await pipeline.run("doc-456") == []
