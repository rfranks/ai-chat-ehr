"""Patient anonymization pipeline for Firestore backed documents.

The pipeline performs the following high level steps:

1. Retrieve a patient document from Firestore.
2. Normalise keys to ``snake_case`` and coerce the payload into the
   :class:`shared.models.PatientRecord` schema.
3. Apply deterministic anonymisation rules to fields that may contain
   protected health information.
4. Map the anonymised payload to a set of database columns defined by a DDL
   mapping and execute the corresponding INSERT statement through the
   :class:`~services.anonymizer.app.clients.postgres_repository.PostgresRepository`.

The implementation favours composability: callers can customise which fields
are anonymised and how database columns are populated by providing mapping
rules.  Sensible defaults cover the common paths required by the anonymiser
service while still allowing tests to provide lightweight fakes.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, Mapping, MutableMapping, Sequence
import json
import re
from copy import deepcopy

from shared.models import PatientRecord
from shared.observability.logger import get_logger

from .resilience import RetryPolicy, call_async_with_retry, call_with_retry

from ..anonymization.replacement import ReplacementContext, apply_replacement
from ..clients import FirestoreClient, FirestorePatientDocument
from ..clients.postgres_repository import PostgresRepository

__all__ = [
    "ColumnResolver",
    "FieldRule",
    "PatientDocumentNotFoundError",
    "PatientPipeline",
    "PipelineContext",
    "PipelineRunSummary",
    "ReplacementSummary",
    "build_address_component_resolver",
    "build_path_resolver",
]


ColumnResolver = Callable[[Mapping[str, Any], "PipelineContext"], Any]


logger = get_logger(__name__)


@dataclass(slots=True, frozen=True)
class FieldRule:
    """Description of a field that requires anonymisation."""

    path: tuple[str, ...]
    entity_type: str


@dataclass(slots=True)
class PipelineContext:
    """Additional context exposed to column resolvers."""

    document_id: str
    firestore_document: Mapping[str, Any]
    normalized_document: Mapping[str, Any]
    patient_payload: Mapping[str, Any]
    collection: str | None = None
    anonymized_patient: Mapping[str, Any] | None = None
    replacement_context: ReplacementContext | None = None


@dataclass(slots=True, frozen=True)
class ReplacementSummary:
    """Aggregate information about replacements applied during anonymisation."""

    entity_type: str
    count: int


@dataclass(slots=True, frozen=True)
class PipelineRunSummary:
    """Structured information returned after executing the patient pipeline."""

    document_id: str
    collection: str | None
    anonymized_patient: Mapping[str, Any]
    replacements: tuple[ReplacementSummary, ...]
    repository_results: tuple[dict[str, Any], ...]
    persistence_error: str | None = None

    @property
    def persistence_succeeded(self) -> bool:
        """Return ``True`` when repository writes completed successfully."""

        return self.persistence_error is None


class PatientDocumentNotFoundError(RuntimeError):
    """Raised when the requested Firestore patient document does not exist."""

    def __init__(self, document_id: str) -> None:
        super().__init__(f"Patient document '{document_id}' was not found in Firestore.")
        self.document_id = document_id


_CAMEL_BOUNDARY_1 = re.compile(r"(.)([A-Z][a-z]+)")
_CAMEL_BOUNDARY_2 = re.compile(r"([a-z0-9])([A-Z])")


def _normalize_key(key: str) -> str:
    """Return a ``snake_case`` representation of ``key`` suitable for models."""

    cleaned = key.strip()
    if not cleaned:
        return cleaned
    cleaned = cleaned.replace("-", "_").replace("/", "_").replace(" ", "_")
    cleaned = _CAMEL_BOUNDARY_1.sub(r"\1_\2", cleaned)
    cleaned = _CAMEL_BOUNDARY_2.sub(r"\1_\2", cleaned)
    cleaned = re.sub(r"__+", "_", cleaned)
    return cleaned.lower()


def _normalize_structure(value: Any) -> Any:
    """Recursively convert mapping keys to ``snake_case``."""

    if isinstance(value, Mapping):
        return {
            _normalize_key(str(key)): _normalize_structure(item)
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalize_structure(item) for item in value]
    return value


def _traverse_structure(value: Any, parts: Sequence[str]) -> Any:
    """Traverse ``value`` following ``parts`` returning ``None`` when absent."""

    if not parts:
        return value

    head, *tail = parts

    if head == "*":
        if isinstance(value, Mapping):
            results = [_traverse_structure(item, tail) for item in value.values()]
            return [item for item in results if item is not None]
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            results = [_traverse_structure(item, tail) for item in value]
            return [item for item in results if item is not None]
        return None

    if isinstance(value, Mapping):
        if head not in value:
            return None
        return _traverse_structure(value[head], tail)

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        try:
            index = int(head)
        except ValueError:
            return None
        if index < 0 or index >= len(value):
            return None
        return _traverse_structure(value[index], tail)

    return None


def _serialise_for_column(value: Any) -> Any:
    """Convert complex types into JSON strings for database insertion."""

    if isinstance(value, (Mapping, Sequence)) and not isinstance(value, (str, bytes, bytearray)):
        try:
            return json.dumps(value, sort_keys=True)
        except TypeError:
            # Fallback: coerce non-serialisable values to strings deterministically.
            return json.dumps(_stringify_structure(value), sort_keys=True)
    return value


def _stringify_structure(value: Any) -> Any:
    """Convert a structure into a JSON serialisable representation."""

    if isinstance(value, Mapping):
        return {key: _stringify_structure(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_stringify_structure(item) for item in value]
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="ignore")
    if isinstance(value, (int, float, str)) or value is None:
        return value
    return str(value)


def build_path_resolver(path: str) -> ColumnResolver:
    """Return a :class:`ColumnResolver` extracting values via dotted paths."""

    parts = tuple(part for part in path.split(".") if part)

    def resolver(payload: Mapping[str, Any], context: PipelineContext) -> Any:
        if not parts:
            return None

        head, *tail = parts

        if head == "document_id":
            if tail:
                return None
            return context.document_id

        if head == "raw":
            return _traverse_structure(context.firestore_document, tail)

        if head == "normalized":
            return _traverse_structure(context.normalized_document, tail)

        if head == "patient":
            return _traverse_structure(payload, tail)

        return _traverse_structure(payload, parts)

    return resolver


_ADDRESS_COMPONENT_KEYS = (
    "line1",
    "line2",
    "city",
    "state",
    "postal_code",
)

_STATE_POSTAL_RE = re.compile(
    r"^(?P<state>[A-Za-z]{2})(?:\s+(?P<postal>[0-9A-Za-z-]{3,}))?$"
)


def _normalise_component(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    return cleaned or None


def _split_address_components(address: str | None) -> dict[str, str | None]:
    """Return discrete address components parsed from ``address`` strings."""

    components: dict[str, str | None] = {key: None for key in _ADDRESS_COMPONENT_KEYS}
    if not address:
        return components

    normalised = address.replace("\n", ",").strip()
    if not normalised:
        return components

    parts = [part.strip() for part in re.split(r",+", normalised) if part.strip()]
    if not parts:
        return components

    components["line1"] = _normalise_component(parts[0])

    remaining = parts[1:]
    city: str | None = None
    state_zip_source: str | None = None

    if remaining:
        if len(remaining) >= 2:
            city = remaining[-2]
            state_zip_source = remaining[-1]
            if len(remaining) > 2:
                components["line2"] = _normalise_component(
                    ", ".join(item for item in remaining[:-2] if item)
                )
        else:
            state_zip_source = remaining[-1]
    if city:
        components["city"] = _normalise_component(city)

    if state_zip_source:
        match = _STATE_POSTAL_RE.match(state_zip_source.strip())
        if match:
            components["state"] = _normalise_component(match.group("state"))
            components["postal_code"] = _normalise_component(match.group("postal"))
        else:
            tokens = state_zip_source.split()
            if tokens:
                # Extract postal code when the last token resembles one.
                if re.match(r"^[0-9A-Za-z-]{3,}$", tokens[-1]):
                    components["postal_code"] = _normalise_component(tokens.pop())
                if tokens:
                    components["state"] = _normalise_component(tokens.pop())
                if tokens and components["city"] is None:
                    components["city"] = _normalise_component(" ".join(tokens))

    if components["city"] is None and len(parts) == 2:
        tokens = parts[1].split()
        if len(tokens) >= 3:
            components["city"] = _normalise_component(" ".join(tokens[:-2]))
            if components["state"] is None:
                components["state"] = _normalise_component(tokens[-2])
            if components["postal_code"] is None:
                components["postal_code"] = _normalise_component(tokens[-1])

    return components


def build_address_component_resolver(component: str) -> ColumnResolver:
    """Build a resolver returning a specific component of the demographics address."""

    if component not in _ADDRESS_COMPONENT_KEYS:
        raise ValueError(f"Unsupported address component: {component}")

    def resolver(payload: Mapping[str, Any], _context: PipelineContext) -> Any:
        demographics = payload.get("demographics") if isinstance(payload, Mapping) else None
        address = None
        if isinstance(demographics, Mapping):
            address = demographics.get("address")
        components = _split_address_components(address if isinstance(address, str) else None)
        return components[component]

    return resolver


def _apply_rule(
    target: Any, path: Sequence[str], entity_type: str, context: ReplacementContext
) -> None:
    """Recursively apply ``entity_type`` replacement to ``target`` at ``path``."""

    if not path:
        return

    head, *tail = path

    if isinstance(target, Mapping):
        if head == "*":
            for value in target.values():
                _apply_rule(value, tail, entity_type, context)
            return
        if head not in target:
            return
        if tail:
            _apply_rule(target[head], tail, entity_type, context)
            return
        value = target[head]
        if value is None:
            return
        if isinstance(value, (Mapping, Sequence)) and not isinstance(value, (str, bytes, bytearray)):
            return
        text = str(value)
        target[head] = apply_replacement(entity_type, text, context)
        return

    if isinstance(target, list):
        if head == "*":
            for item in target:
                _apply_rule(item, tail, entity_type, context)
            return
        try:
            index = int(head)
        except ValueError:
            return
        if index < 0 or index >= len(target):
            return
        if tail:
            _apply_rule(target[index], tail, entity_type, context)
            return
        value = target[index]
        if value is None:
            return
        if isinstance(value, (Mapping, Sequence)) and not isinstance(value, (str, bytes, bytearray)):
            return
        text = str(value)
        target[index] = apply_replacement(entity_type, text, context)


DEFAULT_FIELD_RULES: tuple[FieldRule, ...] = (
    FieldRule(("demographics", "first_name"), "PERSON"),
    FieldRule(("demographics", "middle_name"), "PERSON"),
    FieldRule(("demographics", "last_name"), "PERSON"),
    FieldRule(("demographics", "full_name"), "PERSON"),
    FieldRule(("demographics", "address"), "STREET_ADDRESS"),
    FieldRule(("demographics", "phone"), "PHONE_NUMBER"),
    FieldRule(("demographics", "email"), "EMAIL_ADDRESS"),
    FieldRule(("demographics", "mrn"), "MEDICAL_RECORD_NUMBER"),
    FieldRule(("care_team", "*", "name"), "PERSON"),
    FieldRule(("care_team", "*", "organization"), "ORGANIZATION"),
    FieldRule(("encounters", "*", "provider"), "PERSON"),
    FieldRule(("encounters", "*", "location"), "FACILITY_NAME"),
    FieldRule(("clinical_notes", "*", "author"), "PERSON"),
    FieldRule(("additional_notes", "*", "author"), "PERSON"),
)


class PatientPipeline:
    """Co-ordinate retrieval, anonymisation and persistence of patient records."""

    def __init__(
        self,
        firestore_client: FirestoreClient,
        repository: PostgresRepository,
        *,
        ddl_key: str,
        column_mapping: Mapping[str, ColumnResolver | str],
        field_rules: Sequence[FieldRule] | None = None,
        replacement_context_factory: Callable[[], ReplacementContext] | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        if not ddl_key:
            raise ValueError("ddl_key must be provided for the INSERT mapping")
        if not column_mapping:
            raise ValueError("column_mapping must declare at least one column")

        self._firestore = firestore_client
        self._repository = repository
        self._ddl_key = ddl_key
        self._field_rules: tuple[FieldRule, ...] = (
            tuple(field_rules) if field_rules else DEFAULT_FIELD_RULES
        )
        self._context_factory = replacement_context_factory or ReplacementContext
        self._retry_policy = retry_policy or RetryPolicy()

        resolvers: MutableMapping[str, ColumnResolver] = {}
        for column, resolver in column_mapping.items():
            if isinstance(resolver, str):
                resolvers[column] = build_path_resolver(resolver)
            elif callable(resolver):
                resolvers[column] = resolver
            else:
                raise TypeError(
                    "column_mapping values must be dotted paths or callables"
                )
        self._column_resolvers = dict(resolvers)

    async def run(
        self, document_id: str, *, collection: str | None = None
    ) -> list[dict[str, Any]]:
        """Execute the pipeline for ``document_id`` returning repository results."""

        summary = await self.run_with_summary(document_id, collection=collection)
        return list(summary.repository_results)

    async def run_with_summary(
        self, document_id: str, *, collection: str | None = None
    ) -> PipelineRunSummary:
        """Execute the pipeline returning anonymisation metadata and DB results."""

        document = self._fetch_document(document_id, collection=collection)
        normalized_document = _normalize_structure(document.data)
        patient_payload = self._extract_patient_payload(normalized_document)

        context = PipelineContext(
            document_id=document.document_id,
            firestore_document=document.data,
            normalized_document=deepcopy(normalized_document),
            patient_payload=deepcopy(patient_payload),
            collection=collection,
        )

        anonymized_payload = self._anonymize_patient_payload(patient_payload, context)
        context.anonymized_patient = anonymized_payload

        row = self._build_row(anonymized_payload, context)
        repository_results, persistence_error = await self._persist_row(row, context)

        replacements = _summarize_replacements(context.replacement_context)

        return PipelineRunSummary(
            document_id=document.document_id,
            collection=collection,
            anonymized_patient=deepcopy(anonymized_payload),
            replacements=replacements,
            repository_results=repository_results,
            persistence_error=persistence_error,
        )

    def _fetch_document(
        self, document_id: str, *, collection: str | None = None
    ) -> FirestorePatientDocument:
        try:
            document = call_with_retry(
                self._firestore.get_patient_document,
                document_id,
                collection=collection,
                policy=self._retry_policy,
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error(
                "firestore_document_fetch_failed",
                document_id=document_id,
                collection=collection,
                error=str(exc),
            )
            raise
        if document is None:
            raise PatientDocumentNotFoundError(document_id)
        return document

    def _extract_patient_payload(self, normalized: Mapping[str, Any]) -> Mapping[str, Any]:
        """Return a JSON-ready patient payload from ``normalized``."""

        source: Mapping[str, Any]
        if "patient" in normalized and isinstance(normalized["patient"], Mapping):
            source = normalized["patient"]  # type: ignore[index]
        elif "record" in normalized and isinstance(normalized["record"], Mapping):
            source = normalized["record"]  # type: ignore[index]
        else:
            source = normalized

        record = PatientRecord.model_validate(source)
        return record.model_dump(mode="json", by_alias=False, exclude_none=True)

    def _anonymize_patient_payload(
        self, payload: Mapping[str, Any], context: PipelineContext
    ) -> Mapping[str, Any]:
        replacement_context = self._context_factory()
        context.replacement_context = replacement_context

        anonymized = deepcopy(payload)
        for rule in self._field_rules:
            _apply_rule(anonymized, rule.path, rule.entity_type, replacement_context)
        return anonymized

    def _build_row(
        self, payload: Mapping[str, Any], context: PipelineContext
    ) -> Mapping[str, Any]:
        row: dict[str, Any] = {}
        for column, resolver in self._column_resolvers.items():
            value = resolver(payload, context)
            row[column] = _serialise_for_column(value)
        return row

    async def _persist_row(
        self, row: Mapping[str, Any], context: PipelineContext
    ) -> tuple[tuple[dict[str, Any], ...], str | None]:
        try:
            results = await call_async_with_retry(
                self._repository.insert,
                self._ddl_key,
                row,
                policy=self._retry_policy,
            )
        except Exception as exc:
            logger.error(
                "repository_insert_failed",
                document_id=context.document_id,
                ddl_key=self._ddl_key,
                error=str(exc),
            )
            return (), str(exc)

        return tuple(dict(item) for item in results), None


def _summarize_replacements(
    context: ReplacementContext | None,
) -> tuple[ReplacementSummary, ...]:
    if context is None:
        return ()

    counts: Counter[str] = Counter()
    for entity_type, _ in context.cache.keys():
        counts[entity_type.upper()] += 1

    return tuple(
        ReplacementSummary(entity_type=entity, count=count)
        for entity, count in sorted(counts.items())
    )

