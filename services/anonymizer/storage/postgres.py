"""PostgreSQL storage helpers for the anonymizer service."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, fields
from datetime import date, datetime
from typing import Any, Dict, Iterator, Sequence
from uuid import UUID

from services.anonymizer.storage.ddl import load_statements


class StorageError(RuntimeError):
    """Base error for storage layer operations."""


class ConstraintViolationError(StorageError):
    """Raised when a database constraint is violated."""

    def __init__(
        self,
        message: str,
        *,
        constraint: str | None = None,
        detail: str | None = None,
        original: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.constraint = constraint
        self.detail = detail
        self.original = original


JSONLike = Any


@dataclass(slots=True, frozen=True)
class PatientRow:
    """Lightweight representation of a ``patient`` table row."""

    tenant_id: UUID
    facility_id: UUID
    name_first: str
    name_last: str
    gender: str
    status: str
    id: UUID | None = None
    ehr_instance_id: UUID | None = None
    ehr_external_id: str | None = None
    ehr_connection_status: str | None = None
    ehr_last_full_manual_sync_at: datetime | None = None
    dob: date | None = None
    ethnicity_description: str | None = None
    legal_mailing_address: JSONLike = None
    photo_url: str | None = None
    unit_description: str | None = None
    floor_description: str | None = None
    room_description: str | None = None
    bed_description: str | None = None
    admission_time: datetime | None = None
    discharge_time: datetime | None = None
    death_time: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def as_parameters(self) -> Dict[str, Any]:
        """Return a mapping of non-null column values for insertion."""

        params: Dict[str, Any] = {}
        for field in fields(self):
            value = getattr(self, field.name)
            if value is None:
                continue
            params[field.name] = value
        return params


class PostgresStorage:
    """Encapsulates anonymizer PostgreSQL access and schema management."""

    def __init__(
        self,
        dsn: str,
        *,
        min_size: int = 1,
        max_size: int = 10,
        timeout: float | None = None,
        bootstrap_schema: bool | Sequence[str] = False,
    ) -> None:
        try:
            from psycopg_pool import ConnectionPool
        except ImportError as exc:  # pragma: no cover - defensive runtime guard
            raise StorageError(
                "psycopg-pool is required to use PostgresStorage."
            ) from exc

        pool_kwargs: Dict[str, Any] = {"min_size": min_size, "max_size": max_size}
        if timeout is not None:
            pool_kwargs["timeout"] = timeout

        self._pool = ConnectionPool(dsn, **pool_kwargs)
        self._dsn = dsn

        if bootstrap_schema:
            if isinstance(bootstrap_schema, bool):
                ddl_names: Sequence[str] = ("patients",)
            else:
                ddl_names = bootstrap_schema
            self.bootstrap_schema(ddl_names)

    @property
    def dsn(self) -> str:
        """Return the configured DSN for visibility/testing."""

        return self._dsn

    def close(self) -> None:
        """Close the underlying connection pool."""

        self._pool.close()

    @contextmanager
    def connection(self) -> Iterator[Any]:
        """Yield a pooled psycopg connection."""

        try:
            import psycopg  # noqa: F401
        except ImportError as exc:  # pragma: no cover - defensive runtime guard
            raise StorageError("psycopg is required to obtain connections.") from exc

        with self._pool.connection() as conn:
            yield conn

    def bootstrap_schema(self, ddl_names: Sequence[str] | None = None) -> None:
        """Execute DDL files to prepare the anonymizer schema."""

        if ddl_names is None:
            ddl_names = ("patients",)

        statements: list[str] = []
        for name in ddl_names:
            statements.extend(load_statements(name))

        if not statements:
            return

        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                for statement in statements:
                    cur.execute(statement)
            conn.commit()

    def insert_patient(self, record: PatientRow) -> UUID:
        """Insert ``record`` into ``patient`` and return the resulting ``id``."""

        try:
            from psycopg import sql, errors
        except ImportError as exc:  # pragma: no cover - defensive runtime guard
            raise StorageError("psycopg is required to insert patients.") from exc

        params = record.as_parameters()
        if not params:
            raise StorageError("PatientRow does not contain any values for insertion.")

        columns = list(params.keys())
        query = sql.SQL(
            "INSERT INTO {table} ({columns}) VALUES ({values}) RETURNING id"
        ).format(
            table=sql.Identifier("patient"),
            columns=sql.SQL(", ").join(sql.Identifier(name) for name in columns),
            values=sql.SQL(", ").join(sql.Placeholder(name) for name in columns),
        )

        patient_id: Any = None
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(query, params)
                    row = cur.fetchone()
                    if not row or row[0] is None:
                        raise StorageError(
                            "Insert did not return a patient identifier."
                        )
                    patient_id = row[0]
                except errors.IntegrityError as exc:
                    conn.rollback()
                    constraint = getattr(
                        getattr(exc, "diag", None), "constraint_name", None
                    )
                    detail = getattr(getattr(exc, "diag", None), "message_detail", None)
                    message = (
                        detail or "Database constraint violated during patient insert."
                    )
                    raise ConstraintViolationError(
                        message,
                        constraint=constraint,
                        detail=detail,
                        original=exc,
                    ) from exc
                except StorageError:
                    conn.rollback()
                    raise
                else:
                    conn.commit()

        if not isinstance(patient_id, UUID):
            patient_id = UUID(str(patient_id))

        return patient_id


__all__ = [
    "ConstraintViolationError",
    "PatientRow",
    "PostgresStorage",
    "StorageError",
]
