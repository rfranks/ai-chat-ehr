import json
import sys
import types
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if "shared.models" not in sys.modules:
    shared_models_stub = types.ModuleType("shared.models")

    class _StubPatientRecord:
        def __init__(self, payload: dict[str, object]) -> None:
            self._payload = dict(payload)

        @classmethod
        def model_validate(cls, payload: object) -> "_StubPatientRecord":
            if not isinstance(payload, dict):
                raise TypeError("PatientRecord expects a mapping payload")
            return cls(payload)

        def model_dump(
            self,
            *,
            mode: str | None = None,
            by_alias: bool = False,
            exclude_none: bool = True,
        ) -> dict[str, object]:
            if exclude_none:
                return {k: v for k, v in self._payload.items() if v is not None}
            return dict(self._payload)

    shared_models_stub.PatientRecord = _StubPatientRecord  # type: ignore[attr-defined]
    sys.modules["shared.models"] = shared_models_stub

if "shared.observability.logger" not in sys.modules:
    logger_stub = types.ModuleType("shared.observability.logger")

    class _StubLogger:
        def bind(self, *args: object, **kwargs: object) -> "_StubLogger":  # pragma: no cover - stub
            return self

        def info(self, *args: object, **kwargs: object) -> None:  # pragma: no cover - stub
            return None

        def error(self, *args: object, **kwargs: object) -> None:  # pragma: no cover - stub
            return None

    def _get_logger(_name: str) -> _StubLogger:  # pragma: no cover - stub
        return _StubLogger()

    logger_stub.get_logger = _get_logger  # type: ignore[attr-defined]
    sys.modules["shared.observability.logger"] = logger_stub

if "services.anonymizer.app.clients" not in sys.modules:
    clients_stub = types.ModuleType("services.anonymizer.app.clients")

    class _StubFirestoreClient:
        pass

    class _StubFirestoreClientConfig:
        pass

    class _StubFirestorePatientDocument:
        def __init__(self, document_id: str, data: dict[str, object] | None = None) -> None:
            self.document_id = document_id
            self.data = data or {}

    clients_stub.FirestoreClient = _StubFirestoreClient  # type: ignore[attr-defined]
    clients_stub.FirestoreClientConfig = _StubFirestoreClientConfig  # type: ignore[attr-defined]
    clients_stub.FirestorePatientDocument = _StubFirestorePatientDocument  # type: ignore[attr-defined]

    repo_stub = types.ModuleType("services.anonymizer.app.clients.postgres_repository")

    class _StubInsertStatement:
        def __init__(self, table: str, columns: object, returning: object | None = None) -> None:
            self.table = table
            self.columns = tuple(columns)
            self.returning = tuple(returning) if returning else None

        def render(self) -> str:  # pragma: no cover - stub
            return ""

    class _StubPostgresRepository:
        def __init__(self, *args: object, **kwargs: object) -> None:  # pragma: no cover - stub
            return None

        async def insert(self, *args: object, **kwargs: object) -> list[dict[str, object]]:
            raise AssertionError("Repository insert should not be invoked in this test")

    repo_stub.InsertStatement = _StubInsertStatement  # type: ignore[attr-defined]
    repo_stub.PostgresRepository = _StubPostgresRepository  # type: ignore[attr-defined]

    sys.modules["services.anonymizer.app.clients"] = clients_stub
    sys.modules["services.anonymizer.app.clients.postgres_repository"] = repo_stub

if "tenacity" not in sys.modules:
    tenacity_stub = types.ModuleType("tenacity")

    class _Attempt:
        def __enter__(self) -> None:  # pragma: no cover - stub
            return None

        def __exit__(self, exc_type, exc: object, tb: object) -> bool:  # pragma: no cover - stub
            return False

    class _Retrying:
        def __iter__(self):  # pragma: no cover - stub
            self._yielded = False
            return self

        def __next__(self) -> _Attempt:  # pragma: no cover - stub
            if getattr(self, "_yielded", False):
                raise StopIteration
            self._yielded = True
            return _Attempt()

    class _AsyncRetrying:
        def __aiter__(self):  # pragma: no cover - stub
            self._yielded = False
            return self

        async def __anext__(self) -> _Attempt:  # pragma: no cover - stub
            if getattr(self, "_yielded", False):
                raise StopAsyncIteration
            self._yielded = True
            return _Attempt()

    def _identity(*args: object, **kwargs: object) -> object:  # pragma: no cover - stub
        return args[0] if args else None

    tenacity_stub.Retrying = _Retrying  # type: ignore[attr-defined]
    tenacity_stub.AsyncRetrying = _AsyncRetrying  # type: ignore[attr-defined]
    tenacity_stub.retry_if_exception_type = _identity  # type: ignore[attr-defined]
    tenacity_stub.stop_after_attempt = _identity  # type: ignore[attr-defined]
    tenacity_stub.wait_exponential = _identity  # type: ignore[attr-defined]

    sys.modules["tenacity"] = tenacity_stub

from services.anonymizer.app.pipelines.patient_pipeline import (
    PatientPipeline,
    PipelineContext,
    build_address_component_resolver,
)


class _DummyFirestoreClient:
    """Minimal Firestore stub for pipeline construction."""


class _DummyRepository:
    """Repository stub preventing accidental database writes during tests."""

    async def insert(self, *args, **kwargs):  # pragma: no cover - safety net
        raise AssertionError("Repository insert should not be invoked in this test")


COLUMN_MAPPING = {
    "tenant_id": "normalized.tenant_id",
    "facility_id": "normalized.facility_id",
    "ehr_instance_id": "normalized.ehr_instance_id",
    "ehr_external_id": "normalized.ehr_external_id",
    "ehr_connection_status": "normalized.ehr_connection_status",
    "ehr_last_full_manual_sync_at": "normalized.ehr_last_full_manual_sync_at",
    "name_first": "patient.demographics.first_name",
    "name_last": "patient.demographics.last_name",
    "dob": "patient.demographics.date_of_birth",
    "gender": "patient.demographics.gender",
    "ethnicity_description": "patient.demographics.ethnicity",
    "legal_mailing_address": "normalized.legal_mailing_address",
    "photo_url": "normalized.photo_url",
    "unit_description": "normalized.unit_description",
    "floor_description": "normalized.floor_description",
    "room_description": "normalized.room_description",
    "bed_description": "normalized.bed_description",
    "status": "normalized.status",
    "admission_time": "normalized.admission_time",
    "discharge_time": "normalized.discharge_time",
    "death_time": "normalized.death_time",
}


def _build_pipeline() -> PatientPipeline:
    return PatientPipeline(
        firestore_client=_DummyFirestoreClient(),
        repository=_DummyRepository(),
        ddl_key="patients",
        column_mapping=COLUMN_MAPPING,
    )


def _build_context(
    payload: dict[str, object],
    *,
    normalized_overrides: dict[str, object] | None = None,
) -> PipelineContext:
    normalized_document = {"patient": payload}
    if normalized_overrides:
        normalized_document.update(normalized_overrides)

    return PipelineContext(
        document_id="doc-123",
        firestore_document={"patient": payload},
        normalized_document=normalized_document,
        patient_payload=payload,
        collection="patients",
    )


@pytest.mark.parametrize(
    "component,expected",
    [
        ("line1", "123 Main St"),
        ("line2", "Apt 4B"),
        ("city", "Springfield"),
        ("state", "IL"),
        ("postal_code", "62704"),
    ],
)
def test_build_address_component_resolver_returns_expected_component(component, expected):
    payload = {
        "demographics": {
            "address": "123 Main St, Apt 4B, Springfield, IL 62704",
        }
    }
    context = _build_context(payload)
    resolver = build_address_component_resolver(component)

    value = resolver(payload, context)

    assert value == expected


@pytest.mark.parametrize("component", ["", "country", "latitude"])
def test_build_address_component_resolver_rejects_unknown_component(component):
    with pytest.raises(ValueError):
        build_address_component_resolver(component)


def test_build_row_serializes_payloads_and_populates_all_columns():
    pipeline = _build_pipeline()
    payload = {
        "demographics": {
            "first_name": "Jane",
            "last_name": "Doe",
            "date_of_birth": "1985-02-14",
            "gender": "female",
            "ethnicity": "Not Hispanic or Latino",
        }
    }
    normalized_overrides = {
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "facility_id": "00000000-0000-0000-0000-000000000002",
        "ehr_instance_id": "00000000-0000-0000-0000-000000000003",
        "ehr_external_id": "external-123",
        "ehr_connection_status": "connected",
        "ehr_last_full_manual_sync_at": "2023-07-01T08:15:00Z",
        "legal_mailing_address": {
            "line1": "123 Main St",
            "city": "Springfield",
            "state": "IL",
            "postalCode": "62704",
        },
        "photo_url": "https://example.org/patient.jpg",
        "unit_description": "ICU",
        "floor_description": "4th Floor",
        "room_description": "Room 12",
        "bed_description": "Bed A",
        "status": "admitted",
        "admission_time": "2023-07-01T09:00:00Z",
        "discharge_time": None,
        "death_time": None,
    }
    context = _build_context(payload, normalized_overrides=normalized_overrides)

    row = pipeline._build_row(payload, context)

    assert set(row) == set(COLUMN_MAPPING)

    assert row["tenant_id"] == normalized_overrides["tenant_id"]
    assert row["facility_id"] == normalized_overrides["facility_id"]
    assert row["ehr_instance_id"] == normalized_overrides["ehr_instance_id"]
    assert row["ehr_external_id"] == normalized_overrides["ehr_external_id"]
    assert (
        row["ehr_connection_status"] == normalized_overrides["ehr_connection_status"]
    )
    assert (
        row["ehr_last_full_manual_sync_at"]
        == normalized_overrides["ehr_last_full_manual_sync_at"]
    )
    assert row["name_first"] == payload["demographics"]["first_name"]
    assert row["name_last"] == payload["demographics"]["last_name"]
    assert row["dob"] == payload["demographics"]["date_of_birth"]
    assert row["gender"] == payload["demographics"]["gender"]
    assert row["ethnicity_description"] == payload["demographics"]["ethnicity"]

    assert json.loads(row["legal_mailing_address"]) == normalized_overrides[
        "legal_mailing_address"
    ]

    assert row["photo_url"] == normalized_overrides["photo_url"]
    assert row["unit_description"] == normalized_overrides["unit_description"]
    assert row["floor_description"] == normalized_overrides["floor_description"]
    assert row["room_description"] == normalized_overrides["room_description"]
    assert row["bed_description"] == normalized_overrides["bed_description"]
    assert row["status"] == normalized_overrides["status"]
    assert row["admission_time"] == normalized_overrides["admission_time"]
    assert row["discharge_time"] is None
    assert row["death_time"] is None

    for key in ("tenant_id", "facility_id", "name_first", "name_last", "gender", "status"):
        assert row[key] is not None
