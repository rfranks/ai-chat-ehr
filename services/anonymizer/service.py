"""Patient ingestion helpers for the anonymizer service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from uuid import UUID, NAMESPACE_URL, uuid5

from pydantic import ValidationError

from services.anonymizer.firestore.client import (
    FirestoreDataSource,
    create_firestore_data_source,
)
from services.anonymizer.models.firestore import (
    FirestoreAddress,
    FirestoreCoverage,
    FirestorePatientDocument,
)
from services.anonymizer.models.postgres import PatientRow as PatientModel
from services.anonymizer.presidio_engine import PresidioAnonymizerEngine
from services.anonymizer.storage.postgres import (
    ConstraintViolationError,
    PatientRow as StoragePatientRow,
    PostgresStorage,
    StorageError,
)

ENV_POSTGRES_DSN = "ANONYMIZER_POSTGRES_DSN"
DEFAULT_PATIENT_STATUS = "inactive"


class PatientProcessingError(RuntimeError):
    """Base error raised when a patient cannot be processed."""


class PatientNotFoundError(PatientProcessingError):
    """Raised when the requested patient document does not exist."""


class DuplicatePatientError(PatientProcessingError):
    """Raised when a duplicate patient is detected during insertion."""


class ServiceConfigurationError(PatientProcessingError):
    """Raised when dependencies for the anonymizer service are misconfigured."""


@dataclass(slots=True)
class _ServiceDependencies:
    firestore: FirestoreDataSource
    anonymizer: PresidioAnonymizerEngine
    storage: PostgresStorage


_dependencies: _ServiceDependencies | None = None


def configure_service(
    *,
    firestore: FirestoreDataSource | None = None,
    anonymizer: PresidioAnonymizerEngine | None = None,
    storage: PostgresStorage | None = None,
) -> None:
    """Configure global service dependencies for :func:`process_patient`."""

    global _dependencies

    firestore = firestore or create_firestore_data_source()
    anonymizer = anonymizer or PresidioAnonymizerEngine()
    storage = storage or _create_storage_from_env()

    _dependencies = _ServiceDependencies(
        firestore=firestore,
        anonymizer=anonymizer,
        storage=storage,
    )


def _get_dependencies() -> _ServiceDependencies:
    global _dependencies
    if _dependencies is None:
        configure_service()
    assert _dependencies is not None  # mypy/runtime guard
    return _dependencies


def _create_storage_from_env() -> PostgresStorage:
    dsn = os.getenv(ENV_POSTGRES_DSN)
    if not dsn:
        raise ServiceConfigurationError(
            "Postgres DSN must be provided via the ANONYMIZER_POSTGRES_DSN environment variable.",
        )
    return PostgresStorage(dsn)


async def process_patient(
    collection: str,
    document_id: str,
    *,
    firestore: FirestoreDataSource | None = None,
    anonymizer: PresidioAnonymizerEngine | None = None,
    storage: PostgresStorage | None = None,
) -> UUID:
    """Fetch, anonymize, and persist a patient record from Firestore."""

    deps = _resolve_dependencies(firestore=firestore, anonymizer=anonymizer, storage=storage)

    payload = deps.firestore.get_patient(collection, document_id)
    if payload is None:
        raise PatientNotFoundError(
            "Patient document could not be located for the supplied identifier.",
        )

    try:
        document = FirestorePatientDocument.model_validate(payload)
    except ValidationError as exc:  # pragma: no cover - defensive validation
        raise PatientProcessingError("Patient document is malformed and cannot be processed.") from exc

    anonymized = _anonymize_document(deps.anonymizer, document)
    patient_row = _convert_to_patient_row(
        original=document,
        anonymized=anonymized,
        document_id=document_id,
    )

    try:
        return deps.storage.insert_patient(patient_row)
    except ConstraintViolationError as exc:
        raise DuplicatePatientError(
            "An anonymized patient record already exists for this facility and EHR source.",
        ) from exc
    except StorageError as exc:  # pragma: no cover - defensive runtime guard
        raise PatientProcessingError("Failed to persist the anonymized patient record.") from exc


def _resolve_dependencies(
    *,
    firestore: FirestoreDataSource | None,
    anonymizer: PresidioAnonymizerEngine | None,
    storage: PostgresStorage | None,
) -> _ServiceDependencies:
    if firestore or anonymizer or storage:
        if firestore is None:
            raise ServiceConfigurationError("A Firestore data source must be provided when overriding dependencies.")
        if storage is None:
            raise ServiceConfigurationError("A Postgres storage instance must be provided when overriding dependencies.")
        anonymizer = anonymizer or PresidioAnonymizerEngine()
        return _ServiceDependencies(firestore=firestore, anonymizer=anonymizer, storage=storage)

    return _get_dependencies()


def _anonymize_document(
    engine: PresidioAnonymizerEngine, document: FirestorePatientDocument
) -> FirestorePatientDocument:
    anonymized = document.model_copy(deep=True)

    anonymized.name.first = _anonymize_text(engine, anonymized.name.first)
    anonymized.name.middle = _anonymize_text(engine, anonymized.name.middle)
    anonymized.name.last = _anonymize_text(engine, anonymized.name.last)
    anonymized.name.prefix = _anonymize_text(engine, anonymized.name.prefix)
    anonymized.name.suffix = _anonymize_text(engine, anonymized.name.suffix)

    if anonymized.facility_name:
        anonymized.facility_name = _anonymize_text(engine, anonymized.facility_name)
    if anonymized.facility_id:
        anonymized.facility_id = _anonymize_text(engine, anonymized.facility_id)
    if anonymized.tenant_name:
        anonymized.tenant_name = _anonymize_text(engine, anonymized.tenant_name)
    if anonymized.tenant_id:
        anonymized.tenant_id = _anonymize_text(engine, anonymized.tenant_id)

    if anonymized.ehr:
        anonymized.ehr.provider = _anonymize_text(engine, anonymized.ehr.provider)
        anonymized.ehr.instance_id = _anonymize_text(engine, anonymized.ehr.instance_id)
        anonymized.ehr.patient_id = _anonymize_text(engine, anonymized.ehr.patient_id)
        anonymized.ehr.facility_id = _anonymize_text(engine, anonymized.ehr.facility_id)

    anonymized.coverages = [
        _anonymize_coverage(engine, coverage) for coverage in anonymized.coverages
    ]

    return anonymized


def _anonymize_coverage(
    engine: PresidioAnonymizerEngine, coverage: FirestoreCoverage
) -> FirestoreCoverage:
    coverage = coverage.model_copy(deep=True)

    coverage.member_id = _anonymize_text(engine, coverage.member_id)
    coverage.payer_name = _anonymize_text(engine, coverage.payer_name)
    coverage.payer_id = _anonymize_text(engine, coverage.payer_id)
    coverage.relationship_to_subscriber = _anonymize_text(
        engine, coverage.relationship_to_subscriber
    )
    coverage.first_name = _anonymize_text(engine, coverage.first_name)
    coverage.last_name = _anonymize_text(engine, coverage.last_name)
    coverage.gender = _anonymize_text(engine, coverage.gender)
    coverage.alt_payer_name = _anonymize_text(engine, coverage.alt_payer_name)
    coverage.insurance_type = _anonymize_text(engine, coverage.insurance_type)

    if coverage.address:
        coverage.address = _anonymize_address(engine, coverage.address)

    return coverage


def _anonymize_address(
    engine: PresidioAnonymizerEngine, address: FirestoreAddress
) -> FirestoreAddress:
    address = address.model_copy(deep=True)

    address.address_line1 = _anonymize_text(engine, address.address_line1)
    address.address_line2 = _anonymize_text(engine, address.address_line2)
    address.city = _anonymize_text(engine, address.city)
    address.state = _anonymize_text(engine, address.state)
    address.postal_code = _anonymize_text(engine, address.postal_code)
    address.country = _anonymize_text(engine, address.country)

    return address


def _anonymize_text(engine: PresidioAnonymizerEngine, value: str | None) -> str | None:
    if not value:
        return value
    return engine.anonymize(value)


def _convert_to_patient_row(
    *,
    original: FirestorePatientDocument,
    anonymized: FirestorePatientDocument,
    document_id: str,
) -> StoragePatientRow:
    tenant_uuid = _coerce_uuid(original.tenant_id, fallback=f"tenant:{document_id}")
    facility_uuid = _coerce_uuid(original.facility_id, fallback=f"facility:{document_id}")
    ehr_instance_uuid: UUID | None = None
    ehr_external_id: str | None = None
    ehr_connection_status: str | None = None

    if original.ehr and (original.ehr.instance_id or original.ehr.patient_id):
        ehr_connection_status = "connected"
        if original.ehr.instance_id:
            ehr_instance_uuid = _coerce_uuid(
                original.ehr.instance_id,
                fallback=f"ehr-instance:{document_id}",
            )
        if anonymized.ehr and anonymized.ehr.patient_id:
            ehr_external_id = anonymized.ehr.patient_id

    legal_address = _extract_address(anonymized)

    patient_model = PatientModel(
        tenant_id=tenant_uuid,
        facility_id=facility_uuid,
        ehr_instance_id=ehr_instance_uuid,
        ehr_external_id=ehr_external_id,
        ehr_connection_status=ehr_connection_status,
        name_first=anonymized.name.first,
        name_last=anonymized.name.last,
        gender=(anonymized.gender or "unknown").lower(),
        status=DEFAULT_PATIENT_STATUS,
        dob=None,
        legal_mailing_address=legal_address,
    )

    return StoragePatientRow(**patient_model.model_dump())


def _coerce_uuid(value: str | None, *, fallback: str) -> UUID:
    token = (value or fallback).strip()
    if not token:
        token = fallback
    try:
        return UUID(token)
    except (ValueError, TypeError):
        return uuid5(NAMESPACE_URL, token)


def _extract_address(document: FirestorePatientDocument) -> dict[str, Any] | None:
    for coverage in document.coverages:
        if coverage.address:
            payload = coverage.address.model_dump(exclude_none=True)
            if payload:
                return payload
    return None


__all__ = [
    "DuplicatePatientError",
    "PatientProcessingError",
    "PatientNotFoundError",
    "ServiceConfigurationError",
    "configure_service",
    "process_patient",
]
