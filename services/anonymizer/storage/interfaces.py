"""Protocol definitions for anonymizer storage backends."""

from __future__ import annotations

from typing import Protocol, TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:  # pragma: no cover - import for type checking only
    from services.anonymizer.storage.postgres import PatientRow


class PatientStorage(Protocol):
    """Protocol implemented by anonymizer storage backends."""

    def insert_patient(self, record: "PatientRow") -> UUID:
        """Persist ``record`` and return the resulting patient identifier."""


__all__ = ["PatientStorage"]
