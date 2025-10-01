"""Utilities for loading Firestore document fixtures for the anonymizer service."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

_FIXTURE_DIRECTORY = Path(__file__).parent.parent / "firestore_fixtures" / "patients"


class FixtureLoadError(RuntimeError):
    """Raised when Firestore document fixtures cannot be loaded from disk."""

    def __init__(
        self,
        errors: list[str],
        fixtures: dict[str, Mapping[str, Any]] | None = None,
    ) -> None:
        message = "Failed to load Firestore fixtures:\n" + "\n".join(errors)
        super().__init__(message)
        self.errors = errors
        self.fixtures: dict[str, Mapping[str, Any]] = fixtures or {}


def load_document_fixtures(paths: Iterable[Path]) -> dict[str, Mapping[str, Any]]:
    """Load Firestore document fixtures from the provided iterable of paths."""

    fixtures: dict[str, Mapping[str, Any]] = {}
    errors: list[str] = []

    for path in paths:
        if path.suffix.lower() != ".json":
            errors.append(f"{path}: filename must end with '.json'")
            continue

        document_id = path.stem
        if not document_id:
            errors.append(f"{path}: filename must include a document identifier")
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

        if document_id in fixtures:
            errors.append(
                f"{path}: duplicate document identifier '{document_id}' in fixture set"
            )
            continue

        fixtures[document_id] = payload

    if errors:
        raise FixtureLoadError(errors, fixtures)

    return fixtures


def discover_fixture_paths() -> list[Path]:
    """Return sorted JSON fixture paths from the default fixtures directory."""

    if not _FIXTURE_DIRECTORY.exists():
        return []

    return sorted(
        path for path in _FIXTURE_DIRECTORY.glob("*.json") if path.is_file()
    )


__all__ = ["FixtureLoadError", "load_document_fixtures", "discover_fixture_paths"]
