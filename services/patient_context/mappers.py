"""Utilities for normalizing raw EMR payloads into service models."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from shared.llm.chains import DEFAULT_PROMPT_CATEGORIES
from shared.models import EHRPatientContext, PatientRecord

_CAMEL_BOUNDARY_1 = re.compile(r"(.)([A-Z][a-z]+)")
_CAMEL_BOUNDARY_2 = re.compile(r"([a-z0-9])([A-Z])")

_CATEGORY_SLUG_MAP: dict[str, str] = {
    category.slug.casefold(): category.slug for category in DEFAULT_PROMPT_CATEGORIES
}

_CATEGORY_FIELD_MAP: dict[str, frozenset[str]] = {
    "patientDetail": frozenset({"demographics"}),
    "labs": frozenset({"lab_results"}),
    "testResults": frozenset({"clinical_documents"}),
    "vitals": frozenset({"vital_signs"}),
    "notes": frozenset({"clinical_notes", "additional_notes"}),
    "medications": frozenset({"medications"}),
    "medicationAdministration": frozenset(),
    "orders": frozenset(),
    "allergies": frozenset({"allergies"}),
    "problems": frozenset({"problems"}),
    "pastHistory": frozenset({"problems", "procedures"}),
    "familyHistory": frozenset({"family_history"}),
    "socialHistory": frozenset({"social_history"}),
    "immunizations": frozenset({"immunizations"}),
    "encounters": frozenset({"encounters"}),
    "careTeam": frozenset({"care_team"}),
    "procedures": frozenset({"procedures"}),
    "linesDrainsAirways": frozenset(),
    "intakeOutput": frozenset(),
    "flowsheets": frozenset({"vital_signs"}),
    "microbiology": frozenset({"lab_results"}),
    "pathology": frozenset({"clinical_documents"}),
    "radiologyMedia": frozenset({"imaging"}),
    "genomics": frozenset({"clinical_documents"}),
    "riskScores": frozenset({"clinical_documents"}),
    "carePlans": frozenset({"plan", "goals", "follow_up_actions"}),
    "advanceDirectives": frozenset({"clinical_documents"}),
    "nutrition": frozenset({"clinical_documents"}),
    "respiratorySupport": frozenset({"clinical_documents"}),
    "woundCare": frozenset({"clinical_documents"}),
    "therapies": frozenset({"clinical_documents"}),
    "consults": frozenset({"clinical_notes"}),
    "scheduling": frozenset({"follow_up_actions"}),
    "insurance": frozenset({"clinical_documents"}),
    "billing": frozenset({"clinical_documents"}),
    "communications": frozenset({"additional_notes"}),
    "consents": frozenset({"clinical_documents"}),
    "patientEducation": frozenset({"clinical_documents"}),
}

_ALWAYS_INCLUDED_FIELDS: frozenset[str] = frozenset(
    {
        "demographics",
        "chief_complaint",
        "history_of_present_illness",
        "assessment",
        "plan",
    }
)


def _normalize_key(key: str) -> str:
    """Return a ``snake_case`` representation of ``key``."""

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


def map_patient_record(payload: Mapping[str, Any] | None) -> PatientRecord:
    """Convert a raw patient record payload into a :class:`PatientRecord`."""

    if payload is None:
        raise ValueError("Patient record payload is empty")
    normalized = _normalize_structure(payload)
    return PatientRecord.model_validate(normalized)


def map_patient_context(payload: Mapping[str, Any] | None) -> EHRPatientContext:
    """Convert a raw patient context payload into :class:`EHRPatientContext`."""

    if payload is None:
        raise ValueError("Patient context payload is empty")
    normalized = _normalize_structure(payload)
    return EHRPatientContext.model_validate(normalized)


def filter_context_by_categories(
    context: EHRPatientContext, categories: Sequence[str] | None
) -> EHRPatientContext:
    """Return a copy of ``context`` filtered to ``categories``.

    Unknown or unsupported category slugs are ignored to provide resilient behavior
    for clients. Core demographic and narrative scaffolding is always preserved so
    downstream consumers continue to receive a structurally valid payload.
    """

    if not categories:
        return context.model_copy(deep=True)

    resolved: list[str] = []
    seen: set[str] = set()
    for slug in categories:
        if not isinstance(slug, str):
            continue
        cleaned = slug.strip()
        if not cleaned:
            continue
        candidate = _CATEGORY_SLUG_MAP.get(cleaned.casefold())
        if not candidate or candidate in seen:
            continue
        resolved.append(candidate)
        seen.add(candidate)

    allowed_fields: set[str] = set(_ALWAYS_INCLUDED_FIELDS)
    for slug in resolved:
        allowed_fields.update(_CATEGORY_FIELD_MAP.get(slug, ()))

    if not allowed_fields:
        allowed_fields = set(_ALWAYS_INCLUDED_FIELDS)

    payload = context.model_dump()
    filtered_payload = {
        field: payload.get(field) for field in allowed_fields if field in payload
    }
    return EHRPatientContext.model_validate(filtered_payload)


__all__ = [
    "filter_context_by_categories",
    "map_patient_context",
    "map_patient_record",
]
