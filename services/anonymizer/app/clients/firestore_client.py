"""Firestore client utilities for the anonymizer service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from pydantic import BaseModel

try:  # pragma: no cover - optional dependency at runtime
    from google.cloud import firestore
    from google.oauth2 import service_account
except ImportError:  # pragma: no cover - handled lazily when client is used
    firestore = None  # type: ignore[assignment]
    service_account = None  # type: ignore[assignment]


class FirestorePatientDocument(BaseModel):
    """Typed representation of a patient document stored in Firestore."""

    document_id: str
    data: Dict[str, Any]


@dataclass
class FirestoreClientConfig:
    """Configuration values required to initialise the Firestore client."""

    project_id: Optional[str] = None
    default_collection: Optional[str] = None
    credentials_path: Optional[str] = None
    credentials_info: Optional[Dict[str, Any]] = None


class FirestoreClient:
    """Wrapper around :mod:`google.cloud.firestore` providing typed accessors."""

    def __init__(self, config: FirestoreClientConfig | None = None) -> None:
        self._config = config or FirestoreClientConfig()
        self._client: Optional["firestore.Client"] = None

    def get_patient_document(
        self,
        document_id: str,
        collection: Optional[str] = None,
    ) -> Optional[FirestorePatientDocument]:
        """Fetch a patient document from Firestore.

        Args:
            document_id: Identifier of the Firestore document.
            collection: Optional override for the collection name. When omitted
                the client's default collection from the configuration is used.

        Returns:
            A :class:`FirestorePatientDocument` instance when the document
            exists, otherwise ``None``.
        """

        client = self._get_client()
        collection_name = collection or self._config.default_collection
        if not collection_name:
            raise ValueError("A collection name must be provided or configured.")

        doc_ref = client.collection(collection_name).document(document_id)
        snapshot = doc_ref.get()
        if not snapshot.exists:
            return None

        return FirestorePatientDocument(
            document_id=snapshot.id,
            data=snapshot.to_dict() or {},
        )

    def _get_client(self) -> "firestore.Client":
        """Initialise and cache the underlying Firestore client."""

        if self._client is not None:
            return self._client

        if firestore is None:
            raise RuntimeError(
                "google-cloud-firestore is required to use FirestoreClient. "
                "Install it via 'pip install google-cloud-firestore'.",
            )

        credentials = self._build_credentials()
        self._client = firestore.Client(
            project=self._config.project_id,
            credentials=credentials,
        )
        return self._client

    def _build_credentials(self) -> Optional["service_account.Credentials"]:
        """Construct credentials for the Firestore client when provided."""

        if service_account is None:
            return None

        if self._config.credentials_info:
            return service_account.Credentials.from_service_account_info(
                self._config.credentials_info
            )

        if self._config.credentials_path:
            return service_account.Credentials.from_service_account_file(
                self._config.credentials_path
            )

        return None


__all__ = [
    "FirestoreClient",
    "FirestoreClientConfig",
    "FirestorePatientDocument",
]
