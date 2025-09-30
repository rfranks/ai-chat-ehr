"""Client helpers for external anonymizer integrations."""

from __future__ import annotations

from typing import Any

__all__ = [
    "FirestoreClient",
    "FirestoreClientConfig",
    "FirestorePatientDocument",
]


def __getattr__(name: str) -> Any:  # pragma: no cover - thin wrapper
    if name in __all__:
        from .firestore_client import (
            FirestoreClient,
            FirestoreClientConfig,
            FirestorePatientDocument,
        )

        globals().update(
            {
                "FirestoreClient": FirestoreClient,
                "FirestoreClientConfig": FirestoreClientConfig,
                "FirestorePatientDocument": FirestorePatientDocument,
            }
        )
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
