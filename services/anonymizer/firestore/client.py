"""Firestore client abstractions for the anonymizer service."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Iterable, Mapping

from .fixtures import discover_fixture_paths, load_document_fixtures

ENV_DATA_SOURCE = "ANONYMIZER_FIRESTORE_SOURCE"
ENV_CREDENTIALS = "ANONYMIZER_FIRESTORE_CREDENTIALS"
ENV_FIXTURE_DIRECTORY = "ANONYMIZER_FIRESTORE_FIXTURES_DIR"

MODE_FIXTURES = "fixtures"
MODE_CREDENTIALS = "credentials"

PATIENT_COLLECTION = "patients"


class FirestoreConfigurationError(RuntimeError):
    """Raised when Firestore configuration is invalid."""


class FirestoreDataSource(ABC):
    """Interface that encapsulates patient document retrieval from Firestore."""

    @abstractmethod
    def get_patient(self, collection: str, document_id: str) -> Mapping[str, Any] | None:
        """Return the patient document from the provided collection."""


class FixtureFirestoreDataSource(FirestoreDataSource):
    """Firestore data source backed by JSON fixtures on disk."""

    def __init__(
        self,
        *,
        collection: str = PATIENT_COLLECTION,
        fixtures: Mapping[str, Mapping[str, Any]] | None = None,
        fixture_paths: Iterable[Path] | None = None,
    ) -> None:
        if fixtures is None:
            if fixture_paths is None:
                fixture_paths = discover_fixture_paths()
            fixtures = load_document_fixtures(fixture_paths)
        self._collection = collection
        self._fixtures = {document_id: dict(payload) for document_id, payload in fixtures.items()}

    def get_patient(self, collection: str, document_id: str) -> Mapping[str, Any] | None:
        if collection != self._collection:
            return None

        payload = self._fixtures.get(document_id)
        if payload is None:
            return None

        return dict(payload)


class CredentialedFirestoreDataSource(FirestoreDataSource):
    """Placeholder implementation representing a credentialed Firestore client."""

    def __init__(self, *, credentials_path: Path, project_id: str | None = None) -> None:
        self.credentials_path = Path(credentials_path)
        self.project_id = project_id

    def get_patient(self, collection: str, document_id: str) -> Mapping[str, Any] | None:  # pragma: no cover - placeholder
        raise NotImplementedError(
            "Firestore access requires integration with Google Cloud which is not available in this environment."
        )


def _load_fixture_paths_from_env() -> Iterable[Path] | None:
    directory = os.getenv(ENV_FIXTURE_DIRECTORY)
    if not directory:
        return None

    fixture_dir = Path(directory)
    if not fixture_dir.exists():
        raise FirestoreConfigurationError(
            f"Configured fixture directory '{fixture_dir}' does not exist."
        )

    return sorted(path for path in fixture_dir.glob("*.json") if path.is_file())


def create_firestore_data_source() -> FirestoreDataSource:
    """Return a configured Firestore data source based on environment variables."""

    mode = os.getenv(ENV_DATA_SOURCE, MODE_FIXTURES).lower()

    if mode == MODE_FIXTURES:
        fixture_paths = _load_fixture_paths_from_env()
        return FixtureFirestoreDataSource(fixture_paths=fixture_paths)

    if mode == MODE_CREDENTIALS:
        credentials_path = os.getenv(ENV_CREDENTIALS)
        if not credentials_path:
            raise FirestoreConfigurationError(
                "Firestore credentials are required when using the credentialed data source."
            )
        return CredentialedFirestoreDataSource(credentials_path=Path(credentials_path))

    raise FirestoreConfigurationError(
        f"Unsupported Firestore data source mode '{mode}'. Supported modes: {MODE_FIXTURES}, {MODE_CREDENTIALS}."
    )


__all__ = [
    "ENV_CREDENTIALS",
    "ENV_DATA_SOURCE",
    "ENV_FIXTURE_DIRECTORY",
    "MODE_CREDENTIALS",
    "MODE_FIXTURES",
    "PATIENT_COLLECTION",
    "FirestoreDataSource",
    "FixtureFirestoreDataSource",
    "CredentialedFirestoreDataSource",
    "create_firestore_data_source",
    "FirestoreConfigurationError",
]
