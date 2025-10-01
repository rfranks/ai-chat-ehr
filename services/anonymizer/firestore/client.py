"""Firestore client abstractions for the anonymizer service."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Iterable, Mapping

from .fixtures import discover_fixture_paths, load_document_fixtures

ENV_DATA_SOURCE = "ANONYMIZER_FIRESTORE_SOURCE"
ENV_CREDENTIALS = "ANONYMIZER_FIRESTORE_CREDENTIALS"
ENV_PROJECT_ID = "ANONYMIZER_FIRESTORE_PROJECT"
ENV_FIXTURE_DIRECTORY = "ANONYMIZER_FIRESTORE_FIXTURES_DIR"

MODE_FIXTURES = "fixtures"
MODE_CREDENTIALS = "credentials"

PATIENT_COLLECTION = "patients"


class FirestoreConfigurationError(RuntimeError):
    """Raised when Firestore configuration is invalid."""


class FirestoreDataSourceError(RuntimeError):
    """Raised when Firestore access fails in a sanitized manner."""

    def __init__(
        self, message: str, *, context: Mapping[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.context = dict(context or {})


class FirestoreDataSource(ABC):
    """Interface that encapsulates patient document retrieval from Firestore."""

    @abstractmethod
    def get_patient(
        self, collection: str, document_id: str
    ) -> Mapping[str, Any] | None:
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
        self._fixtures = {
            document_id: dict(payload) for document_id, payload in fixtures.items()
        }

    def get_patient(
        self, collection: str, document_id: str
    ) -> Mapping[str, Any] | None:
        if collection != self._collection:
            return None

        payload = self._fixtures.get(document_id)
        if payload is None:
            return None

        return dict(payload)


class CredentialedFirestoreDataSource(FirestoreDataSource):
    """Firestore data source backed by Google Cloud credentials."""

    def __init__(
        self,
        *,
        credentials_path: Path,
        project_id: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.credentials_path = Path(credentials_path)
        self.project_id = project_id
        self._client = client or self._create_client()

    def _create_client(self) -> Any:
        try:
            from google.cloud import firestore  # type: ignore[import]
        except ImportError as exc:  # pragma: no cover - dependency is optional in tests
            raise FirestoreConfigurationError(
                "google-cloud-firestore must be installed to use the credentialed Firestore data source."
            ) from exc

        if not self.credentials_path.exists():
            raise FirestoreConfigurationError(
                f"Firestore credentials file '{self.credentials_path}' does not exist."
            )

        kwargs: dict[str, Any] = {}
        if self.project_id:
            kwargs["project"] = self.project_id

        return firestore.Client.from_service_account_json(
            str(self.credentials_path), **kwargs
        )

    def _raise_sanitized_error(
        self, collection: str, document_id: str, error: Exception
    ) -> None:
        error_type = error.__class__.__name__
        message = (
            "Failed to fetch Firestore document '<redacted>' "
            f"from collection '{collection}'. Reason: {error_type}."
        )
        context = {
            "collection": collection,
            "document_id": "<redacted>",
            "project_id": self.project_id,
            "error_type": error_type,
        }
        raise FirestoreDataSourceError(message, context=context) from None

    def get_patient(
        self, collection: str, document_id: str
    ) -> Mapping[str, Any] | None:
        try:
            document_reference = self._client.collection(collection).document(
                document_id
            )
            snapshot = document_reference.get()
        except (
            Exception
        ) as exc:  # pragma: no cover - error paths validated via unit tests
            self._raise_sanitized_error(collection, document_id, exc)
        if not getattr(snapshot, "exists", False):
            return None

        payload = snapshot.to_dict()
        if payload is None:
            return None

        return dict(payload)


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

    raw_mode = os.getenv(ENV_DATA_SOURCE)
    mode = (raw_mode.strip() if raw_mode is not None else MODE_FIXTURES).lower()

    if mode == MODE_FIXTURES:
        fixture_paths = _load_fixture_paths_from_env()
        return FixtureFirestoreDataSource(fixture_paths=fixture_paths)

    if mode == MODE_CREDENTIALS:
        credentials_path = os.getenv(ENV_CREDENTIALS)
        if not credentials_path:
            raise FirestoreConfigurationError(
                "Firestore credentials are required when using the credentialed data source."
            )
        project_id = os.getenv(ENV_PROJECT_ID) or None
        return CredentialedFirestoreDataSource(
            credentials_path=Path(credentials_path),
            project_id=project_id,
        )

    raise FirestoreConfigurationError(
        f"Unsupported Firestore data source mode '{mode}'. Supported modes: {MODE_FIXTURES}, {MODE_CREDENTIALS}."
    )


__all__ = [
    "ENV_CREDENTIALS",
    "ENV_DATA_SOURCE",
    "ENV_FIXTURE_DIRECTORY",
    "ENV_PROJECT_ID",
    "MODE_CREDENTIALS",
    "MODE_FIXTURES",
    "PATIENT_COLLECTION",
    "FirestoreDataSource",
    "FixtureFirestoreDataSource",
    "CredentialedFirestoreDataSource",
    "FirestoreDataSourceError",
    "create_firestore_data_source",
    "FirestoreConfigurationError",
]
