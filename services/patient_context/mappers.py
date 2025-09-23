"""Utilities for normalizing raw EMR payloads into service models."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from shared.models import EHRPatientContext, PatientRecord

_CAMEL_BOUNDARY_1 = re.compile(r"(.)([A-Z][a-z]+)")
_CAMEL_BOUNDARY_2 = re.compile(r"([a-z0-9])([A-Z])")


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


__all__ = ["map_patient_context", "map_patient_record"]
