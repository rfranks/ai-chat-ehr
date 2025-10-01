"""Utilities to ensure anonymizer logging never emits PHI."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from itertools import islice
from typing import TYPE_CHECKING, Any, Iterable
from uuid import UUID

try:  # pragma: no cover - optional dependency guard
    from pydantic import BaseModel
except Exception:  # pragma: no cover - pydantic is expected but make defensive
    BaseModel = None  # type: ignore[assignment]

if TYPE_CHECKING:  # pragma: no cover - for static analysis only
    from services.anonymizer.models.firestore import FirestorePatientDocument as _FirestorePatientDocument
else:
    _FirestorePatientDocument = Any

try:  # pragma: no cover - optional dependency guard
    from services.anonymizer.models.firestore import FirestorePatientDocument as _RuntimeFirestorePatientDocument
except Exception:  # pragma: no cover - allow usage without Firestore models installed
    _RuntimeFirestorePatientDocument = None

DEFAULT_ALLOWED_KEYS: frozenset[str] = frozenset(
    {
        "event",
        "status",
        "service",
        "component",
        "phase",
        "reason",
        "code",
        "record_id",
        "recordid",
    }
)


def scrub_for_logging(
    payload: Any,
    *,
    allow_keys: Iterable[str] | None = None,
    redaction: str = "<redacted>",
    max_depth: int = 5,
    max_items: int = 5,
) -> Any:
    """Return ``payload`` converted into a structure safe for log emission.

    Strings, UUIDs, temporal values, and arbitrary objects are replaced with the
    ``redaction`` placeholder unless their key is explicitly allowed. Nested
    collections are summarized to a bounded sample so that the resulting log
    payload only contains high-level metadata while preserving enough structure
    for debugging.
    """

    if max_depth < 0:
        raise ValueError("max_depth must be non-negative")
    if max_items < 1:
        raise ValueError("max_items must be a positive integer")

    allowed = set(DEFAULT_ALLOWED_KEYS)
    if allow_keys:
        allowed.update(key.lower() for key in allow_keys)

    seen: set[int] = set()

    def _preserve_allowed(value: Any, depth: int) -> Any:
        if value is None or isinstance(value, (bool, int, float)):
            return value
        if isinstance(value, Enum):
            enum_value = value.value
            if isinstance(enum_value, (str, int, float, bool)):
                return enum_value
            return value.name
        if isinstance(value, (str, bytes, bytearray, UUID)):
            return str(value)
        return _scrub(value, depth)

    def _scrub(obj: Any, depth: int) -> Any:
        if depth < 0:
            return redaction
        if obj is None or isinstance(obj, (bool, int, float)):
            return obj
        if isinstance(obj, Enum):
            enum_value = obj.value
            if isinstance(enum_value, (str, int, float, bool)):
                return enum_value
            return obj.name
        if isinstance(obj, (str, bytes, bytearray, UUID, date, datetime)):
            return redaction
        if is_dataclass(obj):
            marker = id(obj)
            if marker in seen:
                return redaction
            seen.add(marker)
            try:
                return _scrub(asdict(obj), depth - 1)
            finally:
                seen.remove(marker)
        if BaseModel is not None and isinstance(obj, BaseModel):
            return _scrub(obj.model_dump(mode="python"), depth - 1)
        if isinstance(obj, Mapping):
            marker = id(obj)
            if marker in seen:
                return redaction
            seen.add(marker)
            try:
                sanitized: dict[str, Any] = {}
                for key, value in obj.items():
                    key_str = str(key)
                    lowered = key_str.lower()
                    if lowered in allowed:
                        sanitized[key_str] = _preserve_allowed(value, depth - 1)
                    else:
                        sanitized[key_str] = _scrub(value, depth - 1)
                return sanitized
            finally:
                seen.remove(marker)
        if isinstance(obj, Collection) and not isinstance(obj, (str, bytes, bytearray, Mapping)):
            marker = id(obj)
            if marker in seen:
                return redaction
            seen.add(marker)
            try:
                count = len(obj)
                sample = [_scrub(item, depth - 1) for item in islice(obj, max_items)]
                summary: dict[str, Any] = {"count": count, "__type__": type(obj).__name__}
                if sample:
                    summary["sample"] = sample
                if count > len(sample):
                    summary["truncated"] = True
                return summary
            finally:
                seen.remove(marker)
        return redaction

    return _scrub(payload, max_depth)


def summarize_patient_document(
    document: "_FirestorePatientDocument" | Mapping[str, Any]
) -> dict[str, Any]:
    """Return high-level metadata about a Firestore patient document."""

    data: Mapping[str, Any]
    if _RuntimeFirestorePatientDocument is not None and isinstance(
        document, _RuntimeFirestorePatientDocument
    ):
        data = document.model_dump(mode="python")
    elif _RuntimeFirestorePatientDocument is not None:
        model = _RuntimeFirestorePatientDocument.model_validate(document)
        data = model.model_dump(mode="python")
    elif isinstance(document, Mapping):
        data = document
    else:  # pragma: no cover - defensive guard for unexpected types
        raise TypeError("document must be a mapping or FirestorePatientDocument-like object")

    name = data.get("name") or {}
    if not isinstance(name, Mapping):
        name = {}
    name_components = sum(
        1 for part in (name.get("prefix"), name.get("first"), name.get("middle"), name.get("last"), name.get("suffix")) if part
    )

    coverages = data.get("coverages") or []
    if not isinstance(coverages, Collection):
        coverages = []

    def _coverage_iter() -> Iterable[Mapping[str, Any]]:
        for item in coverages:
            if isinstance(item, Mapping):
                yield item
            elif _RuntimeFirestorePatientDocument is not None and hasattr(item, "model_dump"):
                yield item.model_dump(mode="python")  # type: ignore[call-arg]

    coverage_items = list(_coverage_iter())

    return {
        "name_components": name_components,
        "has_dob": bool(data.get("dob")),
        "has_gender": bool(data.get("gender")),
        "coverage_count": len(coverage_items),
        "coverages_with_member_id": sum(1 for coverage in coverage_items if coverage.get("member_id")),
        "coverages_with_address": sum(1 for coverage in coverage_items if coverage.get("address")),
        "ehr_metadata_present": bool(data.get("ehr")),
        "facility_metadata_present": bool(data.get("facility_id") or data.get("facility_name")),
        "tenant_metadata_present": bool(data.get("tenant_id") or data.get("tenant_name")),
    }


__all__ = ["scrub_for_logging", "summarize_patient_document"]
