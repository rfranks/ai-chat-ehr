"""Repository abstractions for retrieving patient data from an EMR system."""

from __future__ import annotations

import json
import warnings
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable, Mapping

_FIXTURE_DIRECTORY = Path(__file__).parent / "fixtures" / "patients"


class FixtureLoadError(RuntimeError):
    """Raised when patient fixtures cannot be loaded from disk."""

    def __init__(
        self,
        errors: list[str],
        fixtures: dict[str, dict[str, Mapping[str, Any]]] | None = None,
    ) -> None:
        message = "Failed to load patient fixtures:\n" + "\n".join(errors)
        super().__init__(message)
        self.errors = errors
        self.fixtures: dict[str, dict[str, Mapping[str, Any]]] = fixtures or {}


def _infer_fixture_type(filename: str) -> str | None:
    filename = filename.lower()
    if filename.endswith("_record.json"):
        return "record"
    if filename.endswith("_context.json"):
        return "context"
    return None


def _extract_patient_id(payload: Mapping[str, Any]) -> str | None:
    demographics = payload.get("demographics")
    if not isinstance(demographics, Mapping):
        return None
    patient_id = demographics.get("patientId")
    if isinstance(patient_id, str) and patient_id:
        return patient_id
    return None


def load_patient_fixtures(
    paths: Iterable[Path],
) -> dict[str, dict[str, Mapping[str, Any]]]:
    """Load patient fixtures from the provided iterable of filesystem paths."""

    fixtures: dict[str, dict[str, Mapping[str, Any]]] = {}
    errors: list[str] = []

    for path in paths:
        fixture_type = _infer_fixture_type(path.name)
        if fixture_type is None:
            errors.append(
                f"{path}: filename must end with '_record.json' or '_context.json'"
            )
            continue

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            errors.append(f"{path}: {exc.strerror or 'file not found'}")
            continue
        except json.JSONDecodeError as exc:
            errors.append(f"{path}: invalid JSON ({exc.msg})")
            continue

        if not isinstance(payload, Mapping):
            errors.append(f"{path}: top-level JSON payload must be an object")
            continue

        patient_id = _extract_patient_id(payload)
        if not patient_id:
            errors.append(
                f"{path}: missing patient identifier in demographics.patientId"
            )
            continue

        fixtures.setdefault(patient_id, {})[fixture_type] = payload  # type: ignore[index]

    if errors:
        raise FixtureLoadError(errors, fixtures)

    return fixtures


def _discover_fixture_paths() -> list[Path]:
    if not _FIXTURE_DIRECTORY.exists():
        return []
    return sorted(path for path in _FIXTURE_DIRECTORY.glob("*.json") if path.is_file())


_PATIENT_FIXTURES: dict[str, dict[str, Mapping[str, Any]]]

try:
    _PATIENT_FIXTURES = load_patient_fixtures(_discover_fixture_paths())
except FixtureLoadError as exc:  # pragma: no cover - warning path
    warnings.warn(str(exc))
    _PATIENT_FIXTURES = exc.fixtures


class EMRRepository:
    """Repository for retrieving patient data from an electronic medical record."""

    async def fetch_patient_record(self, patient_id: str) -> Mapping[str, Any] | None:
        """Return a longitudinal patient record for ``patient_id`` if known."""

        patient = _PATIENT_FIXTURES.get(patient_id)
        if not patient:
            return None
        record = patient.get("record")
        if not isinstance(record, Mapping):
            return None
        return deepcopy(record)

    async def fetch_patient_context(self, patient_id: str) -> Mapping[str, Any] | None:
        """Return a curated patient context payload for ``patient_id`` if known."""

        patient = _PATIENT_FIXTURES.get(patient_id)
        if not patient:
            return None
        context = patient.get("context")
        if not isinstance(context, Mapping):
            return None
        return deepcopy(context)


__all__ = ["EMRRepository", "FixtureLoadError", "load_patient_fixtures"]
