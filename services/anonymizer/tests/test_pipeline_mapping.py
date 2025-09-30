"""Tests validating pipeline column mapping utilities."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

pytest.importorskip("pydantic")

from services.anonymizer.app.pipelines.patient_pipeline import (
    PatientPipeline,
    PipelineContext,
    build_path_resolver,
)


def test_build_path_resolver_handles_special_roots() -> None:
    payload = {"demographics": {"first_name": "Ada"}}
    firestore_document = {"demographics": {"firstName": "Ada"}, "metadata": {"source": "unit"}}
    normalized_document = {
        "demographics": {"first_name": "Ada"},
        "metadata": {"source": "unit"},
    }

    context = PipelineContext(
        document_id="doc-123",
        firestore_document=firestore_document,
        normalized_document=normalized_document,
        patient_payload=payload,
    )

    assert build_path_resolver("document_id")(payload, context) == "doc-123"
    assert build_path_resolver("raw.metadata.source")(payload, context) == "unit"
    assert (
        build_path_resolver("normalized.demographics.first_name")(payload, context)
        == "Ada"
    )
    assert (
        build_path_resolver("patient.demographics.first_name")(payload, context)
        == "Ada"
    )
    assert build_path_resolver("demographics.first_name")(payload, context) == "Ada"


def test_build_row_serialises_complex_values() -> None:
    payload = {"demographics": {"first_name": "Ada"}}
    firestore_document = {"metadata": {"source": "unit"}}

    context = PipelineContext(
        document_id="doc-456",
        firestore_document=firestore_document,
        normalized_document={"patient": payload},
        patient_payload=payload,
    )

    pipeline = PatientPipeline(
        firestore_client=MagicMock(),
        repository=MagicMock(),
        ddl_key="patients",
        column_mapping={
            "document_id": "document_id",
            "first_name": "patient.demographics.first_name",
            "metadata": "raw.metadata",
            "custom": lambda data, ctx: {
                "doc": ctx.document_id,
                "names": [data["demographics"]["first_name"]],
            },
        },
    )

    row = pipeline._build_row(payload, context)

    assert row["document_id"] == "doc-456"
    assert row["first_name"] == "Ada"
    assert json.loads(row["metadata"]) == {"source": "unit"}
    assert json.loads(row["custom"]) == {"doc": "doc-456", "names": ["Ada"]}
