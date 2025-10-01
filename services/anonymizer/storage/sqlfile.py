"""SQL file storage backend for anonymizer dry-run workflows."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping
from uuid import UUID, NAMESPACE_URL, uuid4, uuid5

from services.anonymizer.storage.postgres import PatientRow, StorageError


class SQLFileStorage:
    """Persist anonymized patient rows as SQL statements for review."""

    HEADER = (
        "-- Anonymizer dry-run output.\n"
        "-- Review the generated INSERT statements before applying them to Postgres.\n\n"
    )

    def __init__(
        self, path: str | Path, *, append: bool = False, encoding: str = "utf-8"
    ) -> None:
        self._path = Path(path)
        self._append = append
        self._encoding = encoding
        self._initialized = False

        if not append and self._path.exists():
            self._path.unlink()

    @property
    def path(self) -> Path:
        """Return the output path for generated SQL statements."""

        return self._path

    def insert_patient(self, record: PatientRow) -> UUID:
        """Write a patient INSERT statement to the configured SQL file."""

        params = record.as_parameters()
        if not params:
            raise StorageError("PatientRow does not contain any values for insertion.")

        statement = self._build_insert_statement(params)
        self._write_statement(statement)

        return self._derive_identifier(params)

    def _build_insert_statement(self, params: Mapping[str, Any]) -> str:
        columns = ", ".join(f'"{name}"' for name in params.keys())
        values = ", ".join(self._format_value(value) for value in params.values())
        return f"INSERT INTO patient ({columns}) VALUES ({values});\n"

    def _format_value(self, value: Any) -> str:
        if isinstance(value, datetime):
            return f"'{value.isoformat(sep=' ', timespec='microseconds')}'"
        if isinstance(value, date):
            return f"'{value.isoformat()}'"
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, UUID):
            return f"'{value}'"
        if isinstance(value, (dict, list)):
            json_payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            return f"'{self._escape_string(json_payload)}'::jsonb"

        text = str(value)
        return f"'{self._escape_string(text)}'"

    def _escape_string(self, value: str) -> str:
        return value.replace("'", "''")

    def _write_statement(self, statement: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)

        if not self._initialized:
            need_header = True
            if self._append and self._path.exists() and self._path.stat().st_size > 0:
                need_header = False
                mode = "a"
            else:
                mode = "a" if self._append else "w"
            with self._path.open(mode, encoding=self._encoding) as handle:
                if need_header:
                    handle.write(self.HEADER)
                handle.write(statement)
            self._initialized = True
            return

        with self._path.open("a", encoding=self._encoding) as handle:
            handle.write(statement)

    def _derive_identifier(self, params: Mapping[str, Any]) -> UUID:
        existing = params.get("id")
        if existing is not None:
            try:
                return existing if isinstance(existing, UUID) else UUID(str(existing))
            except (TypeError, ValueError):
                pass

        seed_parts = [
            str(params.get("facility_id") or ""),
            str(params.get("ehr_instance_id") or ""),
            str(params.get("ehr_external_id") or ""),
        ]
        seed = "|".join(part for part in seed_parts if part)
        if seed:
            return uuid5(NAMESPACE_URL, f"https://chatehr.ai/anonymizer/dry-run/{seed}")

        return uuid4()


__all__ = ["SQLFileStorage"]
