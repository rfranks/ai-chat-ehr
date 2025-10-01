"""Patient ingestion helpers for the anonymizer service."""

from __future__ import annotations

from datetime import date
import hashlib
import os
from dataclasses import dataclass
from typing import Any
from uuid import UUID, NAMESPACE_URL, uuid5

from pydantic import ValidationError

from shared.observability.logger import get_logger

from services.anonymizer.firestore.client import (
    FirestoreDataSource,
    create_firestore_data_source,
)
from services.anonymizer.logging_utils import (
    scrub_for_logging,
    summarize_patient_document,
)
from services.anonymizer.models import TransformationEvent
from services.anonymizer.models.firestore import (
    FirestoreAddress,
    FirestoreCoverage,
    FirestorePatientDocument,
)
from services.anonymizer.models.postgres import PatientRow as PatientModel
from services.anonymizer.presidio_engine import PresidioAnonymizerEngine
from services.anonymizer.storage.interfaces import PatientStorage
from services.anonymizer.storage.postgres import (
    ConstraintViolationError,
    PatientRow as StoragePatientRow,
    PostgresStorage,
    StorageError,
)
from services.anonymizer.storage.sqlfile import SQLFileStorage

ENV_POSTGRES_DSN = "ANONYMIZER_POSTGRES_DSN"
ENV_STORAGE_MODE = "ANONYMIZER_STORAGE_MODE"
ENV_SQL_OUTPUT_PATH = "ANONYMIZER_STORAGE_SQL_PATH"
DEFAULT_PATIENT_STATUS = "inactive"
DEFAULT_SQL_OUTPUT_PATH = "anonymizer_dry_run.sql"
STORAGE_MODE_DATABASE = "database"
STORAGE_MODE_SQL_FILE = "sqlfile"

_STATE_FIPS_PREFIX: dict[str, int] = {
    "AL": 1,
    "AK": 2,
    "AZ": 4,
    "AR": 5,
    "CA": 6,
    "CO": 8,
    "CT": 9,
    "DE": 10,
    "DC": 11,
    "FL": 12,
    "GA": 13,
    "HI": 15,
    "ID": 16,
    "IL": 17,
    "IN": 18,
    "IA": 19,
    "KS": 20,
    "KY": 21,
    "LA": 22,
    "ME": 23,
    "MD": 24,
    "MA": 25,
    "MI": 26,
    "MN": 27,
    "MS": 28,
    "MO": 29,
    "MT": 30,
    "NE": 31,
    "NV": 32,
    "NH": 33,
    "NJ": 34,
    "NM": 35,
    "NY": 36,
    "NC": 37,
    "ND": 38,
    "OH": 39,
    "OK": 40,
    "OR": 41,
    "PA": 42,
    "RI": 44,
    "SC": 45,
    "SD": 46,
    "TN": 47,
    "TX": 48,
    "UT": 49,
    "VT": 50,
    "VA": 51,
    "WA": 53,
    "WV": 54,
    "WI": 55,
    "WY": 56,
    "PR": 72,
}

_STREET_NAMES = (
    "Redwood",
    "Maple",
    "Cedar",
    "Willow",
    "Summit",
    "Riverview",
    "Sunset",
    "Hillcrest",
    "Parkside",
    "Lakeside",
    "Prairie",
    "Riverstone",
    "Oak Grove",
    "Silverpine",
    "Meadowbrook",
)

_STREET_SUFFIXES = (
    "St",
    "Ave",
    "Dr",
    "Ln",
    "Way",
    "Rd",
    "Terrace",
    "Court",
    "Place",
    "Trail",
)

_CITY_NAMES = (
    "Riverton",
    "Oakridge",
    "Fairview",
    "Brookfield",
    "Sunnyvale",
    "Highland",
    "Glenmont",
    "Clearwater",
    "Silverpine",
    "Lakeshore",
    "Grand Harbor",
    "Cedar Grove",
    "Mapleton",
    "Pinecrest",
    "Harborside",
)


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
    storage: PatientStorage


_dependencies: _ServiceDependencies | None = None

logger = get_logger(__name__)


def configure_service(
    *,
    firestore: FirestoreDataSource | None = None,
    anonymizer: PresidioAnonymizerEngine | None = None,
    storage: PatientStorage | None = None,
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


def _create_storage_from_env() -> PatientStorage:
    mode = os.getenv(ENV_STORAGE_MODE)
    if mode:
        mode = mode.strip().lower()
    else:
        mode = STORAGE_MODE_DATABASE

    if mode in {STORAGE_MODE_DATABASE, "postgres", "postgresql"}:
        dsn = os.getenv(ENV_POSTGRES_DSN)
        if not dsn:
            raise ServiceConfigurationError(
                "Postgres DSN must be provided via the ANONYMIZER_POSTGRES_DSN environment variable.",
            )
        return PostgresStorage(dsn)

    if mode in {STORAGE_MODE_SQL_FILE, "sql-file", "file", "dry-run", "dryrun"}:
        output_path = os.getenv(ENV_SQL_OUTPUT_PATH, DEFAULT_SQL_OUTPUT_PATH)
        if not output_path:
            raise ServiceConfigurationError(
                "Dry-run storage mode requires ANONYMIZER_STORAGE_SQL_PATH to specify an output file.",
            )
        return SQLFileStorage(output_path)

    raise ServiceConfigurationError(
        "Unsupported anonymizer storage mode configured via ANONYMIZER_STORAGE_MODE.",
    )


async def process_patient(
    collection: str,
    document_id: str,
    *,
    firestore: FirestoreDataSource | None = None,
    anonymizer: PresidioAnonymizerEngine | None = None,
    storage: PatientStorage | None = None,
) -> tuple[UUID, list[TransformationEvent]]:
    """Fetch, anonymize, and persist a patient record from Firestore.

    Returns a tuple containing the persisted patient UUID along with the
    collected transformation events emitted by the anonymizer engine.
    """

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

    logger.info(
        "Fetched patient document metadata from Firestore.",
        event="anonymizer.patient.document_loaded",
        firestore_reference=scrub_for_logging(
            {
                "collection": collection,
                "document_id": document_id,
                "collection_length": len(collection),
                "document_id_length": len(document_id),
            },
            allow_keys={"collection_length", "document_id_length"},
        ),
        document_summary=summarize_patient_document(document),
    )

    transformation_events: list[TransformationEvent] = []
    anonymized = _anonymize_document(
        deps.anonymizer,
        document,
        transformation_events,
    )
    patient_row = _convert_to_patient_row(
        original=document,
        anonymized=anonymized,
        document_id=document_id,
        event_accumulator=transformation_events,
    )

    try:
        patient_id = deps.storage.insert_patient(patient_row)
        logger.info(
            "Persisted anonymized patient record.",
            event="anonymizer.patient.persisted",
            record=scrub_for_logging({"record_id": patient_id}),
            patient_row=scrub_for_logging(patient_row),
            transformation_event_count=len(transformation_events),
        )
        return patient_id, transformation_events
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
    storage: PatientStorage | None,
) -> _ServiceDependencies:
    if firestore or anonymizer or storage:
        if firestore is None:
            raise ServiceConfigurationError("A Firestore data source must be provided when overriding dependencies.")
        if storage is None:
            raise ServiceConfigurationError("A patient storage instance must be provided when overriding dependencies.")
        anonymizer = anonymizer or PresidioAnonymizerEngine()
        return _ServiceDependencies(firestore=firestore, anonymizer=anonymizer, storage=storage)

    return _get_dependencies()


def _anonymize_document(
    engine: PresidioAnonymizerEngine,
    document: FirestorePatientDocument,
    event_accumulator: list[TransformationEvent] | None = None,
) -> FirestorePatientDocument:
    anonymized = document.model_copy(deep=True)

    anonymized.name.first = _anonymize_text(engine, anonymized.name.first, event_accumulator)
    anonymized.name.middle = _anonymize_text(engine, anonymized.name.middle, event_accumulator)
    anonymized.name.last = _anonymize_text(engine, anonymized.name.last, event_accumulator)
    anonymized.name.prefix = _anonymize_text(engine, anonymized.name.prefix, event_accumulator)
    anonymized.name.suffix = _anonymize_text(engine, anonymized.name.suffix, event_accumulator)

    if anonymized.facility_name:
        anonymized.facility_name = _anonymize_text(
            engine,
            anonymized.facility_name,
            event_accumulator,
        )
    if anonymized.facility_id:
        anonymized.facility_id = _anonymize_text(
            engine,
            anonymized.facility_id,
            event_accumulator,
        )
    if anonymized.tenant_name:
        anonymized.tenant_name = _anonymize_text(
            engine,
            anonymized.tenant_name,
            event_accumulator,
        )
    if anonymized.tenant_id:
        anonymized.tenant_id = _anonymize_text(
            engine,
            anonymized.tenant_id,
            event_accumulator,
        )

    if anonymized.ehr:
        anonymized.ehr.provider = _anonymize_text(
            engine,
            anonymized.ehr.provider,
            event_accumulator,
        )
        anonymized.ehr.instance_id = _anonymize_text(
            engine,
            anonymized.ehr.instance_id,
            event_accumulator,
        )
        anonymized.ehr.patient_id = _anonymize_text(
            engine,
            anonymized.ehr.patient_id,
            event_accumulator,
        )
        anonymized.ehr.facility_id = _anonymize_text(
            engine,
            anonymized.ehr.facility_id,
            event_accumulator,
        )

    anonymized.coverages = [
        _anonymize_coverage(engine, coverage, event_accumulator)
        for coverage in anonymized.coverages
    ]

    return anonymized


def _anonymize_coverage(
    engine: PresidioAnonymizerEngine,
    coverage: FirestoreCoverage,
    event_accumulator: list[TransformationEvent] | None = None,
) -> FirestoreCoverage:
    coverage = coverage.model_copy(deep=True)

    coverage.member_id = _anonymize_text(engine, coverage.member_id, event_accumulator)
    coverage.payer_name = _anonymize_text(engine, coverage.payer_name, event_accumulator)
    coverage.payer_id = _anonymize_text(engine, coverage.payer_id, event_accumulator)
    coverage.relationship_to_subscriber = _anonymize_text(
        engine,
        coverage.relationship_to_subscriber,
        event_accumulator,
    )
    coverage.first_name = _anonymize_text(engine, coverage.first_name, event_accumulator)
    coverage.last_name = _anonymize_text(engine, coverage.last_name, event_accumulator)
    coverage.gender = _anonymize_text(engine, coverage.gender, event_accumulator)
    coverage.alt_payer_name = _anonymize_text(engine, coverage.alt_payer_name, event_accumulator)
    coverage.insurance_type = _anonymize_text(engine, coverage.insurance_type, event_accumulator)

    if coverage.address:
        coverage.address = _anonymize_address(
            engine,
            coverage.address,
            event_accumulator,
        )

    return coverage


def _hash_to_int(*values: str | None, salt: str) -> int:
    """Hash the provided ``values`` into a deterministic integer."""

    payload = "|".join(value or "" for value in values)
    digest = hashlib.sha256(f"{salt}|{payload}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def _synthesize_street(
    *,
    original_line1: str | None,
    reference_values: tuple[str | None, ...],
) -> str:
    """Return a deterministic synthetic street address."""

    seed = _hash_to_int(*reference_values, salt="street")
    number = (seed % 9000) + 100
    name_index = seed % len(_STREET_NAMES)
    suffix_index = (seed // len(_STREET_NAMES)) % len(_STREET_SUFFIXES)
    street = f"{number} {_STREET_NAMES[name_index]} {_STREET_SUFFIXES[suffix_index]}"

    if original_line1 and street.lower() == original_line1.lower():
        name_index = (name_index + 1) % len(_STREET_NAMES)
        suffix_index = (suffix_index + 1) % len(_STREET_SUFFIXES)
        number = ((number + 73) % 9000) + 100
        street = f"{number} {_STREET_NAMES[name_index]} {_STREET_SUFFIXES[suffix_index]}"

    return street


def _synthesize_city(
    *,
    original_city: str | None,
    reference_values: tuple[str | None, ...],
) -> str:
    """Return a deterministic synthetic city name."""

    seed = _hash_to_int(*reference_values, salt="city")
    city_index = seed % len(_CITY_NAMES)
    city = _CITY_NAMES[city_index]

    if original_city and city.lower() == original_city.lower():
        city = _CITY_NAMES[(city_index + 1) % len(_CITY_NAMES)]

    return city


def _synthesize_postal_code(
    *,
    original_postal: str | None,
    state: str | None,
    reference_values: tuple[str | None, ...],
) -> str:
    """Return a deterministic Safe Harbor postal code."""

    seed = _hash_to_int(*reference_values, salt="postal")

    if state and state in _STATE_FIPS_PREFIX:
        prefix = _STATE_FIPS_PREFIX[state]
        digits = seed % 1000
        postal = f"{prefix:02d}{digits:03d}"
        if original_postal and postal == original_postal:
            digits = (digits + 1) % 1000
            postal = f"{prefix:02d}{digits:03d}"
        return postal

    postal = f"{(seed % 90000) + 10000:05d}"
    if original_postal and postal == original_postal:
        alt = ((seed + 1) % 90000) + 10000
        postal = f"{alt:05d}"
    return postal


def _anonymize_address(
    engine: PresidioAnonymizerEngine,
    address: FirestoreAddress,
    event_accumulator: list[TransformationEvent] | None = None,
) -> FirestoreAddress:
    address = address.model_copy(deep=True)

    original_line1 = address.address_line1
    original_city = address.city
    original_postal = address.postal_code
    original_state = (address.state or "").strip() or None
    original_country = (address.country or "").strip() or None

    state_abbr: str | None = None
    if original_state and len(original_state) == 2 and original_state.isalpha():
        state_abbr = original_state.upper()
        address.state = state_abbr
    else:
        address.state = _anonymize_text(engine, original_state, event_accumulator)

    address.country = original_country

    reference_values = (
        original_line1,
        original_city,
        original_postal,
        state_abbr,
        original_country,
    )

    street = _synthesize_street(
        original_line1=original_line1,
        reference_values=reference_values,
    )
    city = _synthesize_city(
        original_city=original_city,
        reference_values=reference_values,
    )
    postal_code = _synthesize_postal_code(
        original_postal=original_postal,
        state=state_abbr,
        reference_values=reference_values,
    )

    address.address_line1 = street
    address.city = city
    address.postal_code = postal_code
    address.address_line2 = _anonymize_text(
        engine, address.address_line2, event_accumulator
    )

    def _record(component: str, value: str) -> None:
        location = f" within {state_abbr}" if state_abbr else ""
        note = f"Synthesized patient mailing {component}{location}: {value}."
        if event_accumulator is not None:
            event_accumulator.append(
                TransformationEvent(
                    entity_type=f"PATIENT_ADDRESS_{component.upper()}",
                    action="synthesize",
                    start=0,
                    end=0,
                    surrogate=note,
                )
            )

    _record("street", street)
    _record("city", city)
    _record("postal_code", postal_code)

    return address


def _anonymize_text(
    engine: PresidioAnonymizerEngine,
    value: str | None,
    event_accumulator: list[TransformationEvent] | None = None,
) -> str | None:
    if not value:
        return value
    if event_accumulator is None:
        return engine.anonymize(value)

    anonymized_text, events = engine.anonymize(value, collect_events=True)
    event_accumulator.extend(events)
    return anonymized_text


def _convert_to_patient_row(
    *,
    original: FirestorePatientDocument,
    anonymized: FirestorePatientDocument,
    document_id: str,
    event_accumulator: list[TransformationEvent] | None = None,
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
        dob=_generalize_date_of_birth(original.dob, event_accumulator=event_accumulator),
        legal_mailing_address=legal_address,
    )

    return StoragePatientRow(**patient_model.model_dump())


def _generalize_date_of_birth(
    dob: date | None,
    *,
    event_accumulator: list[TransformationEvent] | None = None,
) -> date | None:
    """Generalize ``dob`` following the HIPAA Safe Harbor age requirement."""

    if dob is None:
        return None

    today = date.today()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    if age >= 90:
        if event_accumulator is not None:
            event_accumulator.append(
                TransformationEvent(
                    entity_type="PATIENT_DOB",
                    action="suppress",
                    start=0,
                    end=0,
                    surrogate=(
                        "Removed patient date of birth for individuals aged 90 or older."
                    ),
                )
            )
        return None

    generalized = date(dob.year, 1, 1)

    if event_accumulator is not None:
        event_accumulator.append(
            TransformationEvent(
                entity_type="PATIENT_DOB",
                action="generalize",
                start=0,
                end=0,
                surrogate=f"Generalized patient date of birth to {generalized.isoformat()}.",
            )
        )

    return generalized


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
            safe_address: dict[str, Any] = {}
            if coverage.address.address_line1:
                safe_address["street"] = coverage.address.address_line1
            if coverage.address.address_line2:
                safe_address["unit"] = coverage.address.address_line2
            if coverage.address.city:
                safe_address["city"] = coverage.address.city
            if coverage.address.state:
                safe_address["state"] = coverage.address.state
            if coverage.address.postal_code:
                safe_address["postal_code"] = coverage.address.postal_code
            if coverage.address.country:
                safe_address["country"] = coverage.address.country
            if safe_address:
                return safe_address
    return None


__all__ = [
    "DuplicatePatientError",
    "PatientProcessingError",
    "PatientNotFoundError",
    "ServiceConfigurationError",
    "configure_service",
    "process_patient",
]
