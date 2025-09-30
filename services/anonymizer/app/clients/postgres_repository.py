"""Async PostgreSQL repository for the anonymizer service."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Mapping, MutableMapping, Sequence

from sqlalchemy import text
from sqlalchemy.engine import Result
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine


@dataclass(slots=True, frozen=True)
class InsertStatement:
    """Description of an INSERT statement defined in the DDL mapping.

    Attributes:
        table: Target table name.
        columns: Column names expected in the payload. The order is used when
            constructing the SQL statement.
        returning: Optional columns to return from the ``RETURNING`` clause.
    """

    table: str
    columns: Sequence[str]
    returning: Sequence[str] | None = None

    def render(self) -> str:
        """Render the SQL INSERT statement for the mapping."""

        column_sql = ", ".join(self.columns)
        value_sql = ", ".join(f":{column}" for column in self.columns)
        sql = f"INSERT INTO {self.table} ({column_sql}) VALUES ({value_sql})"
        if self.returning:
            sql = f"{sql} RETURNING {', '.join(self.returning)}"
        return sql


DDLMapping = Mapping[str, InsertStatement]


class PostgresRepository:
    """Repository helper for executing INSERT statements on PostgreSQL."""

    def __init__(
        self,
        database_url: str,
        ddl_mapping: DDLMapping,
        *,
        engine: AsyncEngine | None = None,
    ) -> None:
        self._engine: AsyncEngine = engine or create_async_engine(database_url)
        self._ddl_mapping: MutableMapping[str, InsertStatement] = dict(ddl_mapping)

    @asynccontextmanager
    async def transaction(self) -> AsyncConnection:
        """Provide a transactional connection scope."""

        async with self._engine.begin() as connection:
            yield connection

    async def insert(
        self,
        key: str,
        payload: Mapping[str, Any] | Sequence[Mapping[str, Any]],
        *,
        connection: AsyncConnection | None = None,
    ) -> list[dict[str, Any]]:
        """Execute an INSERT defined in the DDL mapping.

        Args:
            key: Identifier in the DDL mapping for the INSERT statement.
            payload: Mapping or sequence of mappings with column values.
            connection: Optional active :class:`AsyncConnection`. When omitted,
                the repository will create a new transaction scope.

        Returns:
            A list of dictionaries containing rows returned from the query. The
            list will be empty when the statement does not declare a
            ``RETURNING`` clause.
        """

        statement = self._ddl_mapping.get(key)
        if statement is None:
            raise KeyError(f"No DDL mapping defined for key '{key}'.")

        rows = self._normalise_rows(statement, payload)
        sql = text(statement.render())

        if connection is None:
            async with self.transaction() as tx:
                result = await tx.execute(sql, rows)
        else:
            result = await connection.execute(sql, rows)

        return self._process_result(statement, result)

    def _normalise_rows(
        self,
        statement: InsertStatement,
        payload: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    ) -> list[Mapping[str, Any]]:
        """Normalise payload into a list of mappings and validate columns."""

        if isinstance(payload, Mapping):
            rows: list[Mapping[str, Any]] = [payload]
        elif isinstance(payload, Sequence):
            rows = [row for row in payload]
        else:
            raise TypeError(
                "Payload must be a mapping or a sequence of mappings for INSERT",
            )

        required = set(statement.columns)
        for row in rows:
            missing = required.difference(row)
            if missing:
                missing_cols = ", ".join(sorted(missing))
                raise ValueError(
                    f"Missing required columns for '{statement.table}': {missing_cols}",
                )
        return rows

    def _process_result(
        self, statement: InsertStatement, result: Result
    ) -> list[dict[str, Any]]:
        """Collect returning rows when defined in the DDL mapping."""

        if not statement.returning:
            return []

        return [dict(row) for row in result.mappings()]

    async def dispose(self) -> None:
        """Dispose of the underlying engine."""

        await self._engine.dispose()


__all__ = ["DDLMapping", "InsertStatement", "PostgresRepository"]
