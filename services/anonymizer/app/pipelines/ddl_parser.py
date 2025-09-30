"""DDL parsing helpers used by anonymizer pipelines.

This module provides a small parser that can read PostgreSQL ``.ddl`` files and
extract metadata for tables and columns.  The resulting metadata is useful when
building INSERT statements dynamically for the anonymizer pipelines.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable, Mapping, MutableMapping, Sequence

try:  # pragma: no cover - optional dependency for tests
    from ..clients.postgres_repository import InsertStatement
except ModuleNotFoundError:  # pragma: no cover - fallback when SQLAlchemy is unavailable
    @dataclass(slots=True, frozen=True)
    class InsertStatement:
        table: str
        columns: Sequence[str]
        returning: Sequence[str] | None = None

        def render(self) -> str:
            column_sql = ", ".join(self.columns)
            value_sql = ", ".join(f":{column}" for column in self.columns)
            sql = f"INSERT INTO {self.table} ({column_sql}) VALUES ({value_sql})"
            if self.returning:
                sql = f"{sql} RETURNING {', '.join(self.returning)}"
            return sql

_CONSTRAINT_PATTERN = re.compile(
    r"\b(NOT\s+NULL|NULL|CONSTRAINT|PRIMARY\s+KEY|UNIQUE|CHECK|REFERENCES)\b",
    re.IGNORECASE,
)
_DEFAULT_PATTERN = re.compile(r"\bDEFAULT\b", re.IGNORECASE)


@dataclass(slots=True, frozen=True)
class ColumnMetadata:
    """Metadata for a table column defined in a DDL file."""

    name: str
    data_type: str
    default: str | None
    nullable: bool
    raw: str

    @property
    def has_default(self) -> bool:
        """Return ``True`` when the column defines a default expression."""

        return self.default is not None

    @property
    def required(self) -> bool:
        """Return ``True`` when the column must receive a value on INSERT."""

        return not self.nullable and self.default is None


@dataclass(slots=True, frozen=True)
class TableMetadata:
    """Metadata describing a database table."""

    schema: str
    name: str
    columns: tuple[ColumnMetadata, ...]
    constraints: tuple[str, ...]

    @property
    def fully_qualified_name(self) -> str:
        """Return the schema qualified table name."""

        return f"{self.schema}.{self.name}" if self.schema else self.name

    def required_columns(self) -> tuple[str, ...]:
        """Return the names of columns that must be provided on INSERT."""

        return tuple(column.name for column in self.columns if column.required)

    def optional_columns(self) -> tuple[str, ...]:
        """Return the names of nullable or defaulted columns."""

        return tuple(column.name for column in self.columns if not column.required)


def load_table_metadata(path: str | Path) -> TableMetadata:
    """Load and parse a ``.ddl`` file into :class:`TableMetadata`."""

    ddl = Path(path).read_text(encoding="utf8")
    return parse_ddl(ddl)


def parse_ddl(ddl: str) -> TableMetadata:
    """Parse the content of a DDL file and return table metadata."""

    match = re.search(
        r"CREATE\s+TABLE\s+(?P<name>[\w\"\.]+)\s*\((?P<body>.*)\)\s*;",
        ddl,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise ValueError("Unable to locate CREATE TABLE statement in DDL content.")

    qualified_name = match.group("name").strip()
    schema, table = _split_schema_table(qualified_name)

    body = match.group("body")
    columns, constraints = _parse_body(body)

    return TableMetadata(schema=schema, name=table, columns=columns, constraints=constraints)


def build_insert_statement(
    metadata: TableMetadata,
    *,
    include_defaulted: bool = True,
    include_nullable: bool = True,
    returning: Sequence[str] | None = None,
) -> InsertStatement:
    """Create an :class:`InsertStatement` using metadata derived from DDL."""

    selected_columns: list[str] = []
    for column in metadata.columns:
        if not include_defaulted and column.has_default:
            continue
        if not include_nullable and column.nullable:
            continue
        selected_columns.append(column.name)

    return InsertStatement(
        table=metadata.fully_qualified_name,
        columns=tuple(selected_columns),
        returning=tuple(returning) if returning else None,
    )


def build_mapping_from_files(
    files: Mapping[str, str | Path] | Iterable[str | Path],
    *,
    include_defaulted: bool = True,
    include_nullable: bool = True,
    returning: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, InsertStatement]:
    """Build a DDL mapping from a collection of ``.ddl`` files.

    Args:
        files: Either a mapping of keys to file paths, or an iterable of file
            paths. When an iterable is provided, the mapping key defaults to the
            stem of the file (e.g. ``patients.ddl`` -> ``"patients"``).
        include_defaulted: When ``False`` columns with default values are
            excluded from the INSERT statement.
        include_nullable: When ``False`` nullable columns are excluded from the
            INSERT statement.
        returning: Optional mapping of keys to column names to include in the
            ``RETURNING`` clause for the generated statements.
    """

    if isinstance(files, Mapping):
        items: Iterable[tuple[str, str | Path]] = files.items()
    else:
        items = ((Path(path).stem, path) for path in files)

    mapping: MutableMapping[str, InsertStatement] = {}
    for key, path in items:
        metadata = load_table_metadata(path)
        returning_columns = returning.get(key) if returning else None
        mapping[str(key)] = build_insert_statement(
            metadata,
            include_defaulted=include_defaulted,
            include_nullable=include_nullable,
            returning=returning_columns,
        )
    return dict(mapping)


def _split_schema_table(qualified_name: str) -> tuple[str, str]:
    if "." in qualified_name:
        schema, table = qualified_name.split(".", 1)
    else:
        schema, table = "", qualified_name
    return schema.strip('"'), table.strip('"')


def _parse_body(body: str) -> tuple[tuple[ColumnMetadata, ...], tuple[str, ...]]:
    columns: list[ColumnMetadata] = []
    constraints: list[str] = []

    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = line.rstrip(",")
        if line.upper().startswith("CONSTRAINT"):
            constraints.append(line)
            continue
        column = _parse_column(line, raw_line)
        columns.append(column)

    return tuple(columns), tuple(constraints)


def _parse_column(line: str, raw: str) -> ColumnMetadata:
    parts = line.split(None, 1)
    if len(parts) != 2:
        raise ValueError(f"Unable to parse column definition: {raw.strip()}")

    name_token, remainder = parts
    name = name_token.strip('"')

    data_type, default, nullable = _parse_column_details(remainder)
    return ColumnMetadata(name=name, data_type=data_type, default=default, nullable=nullable, raw=raw.rstrip())


def _parse_column_details(remainder: str) -> tuple[str, str | None, bool]:
    remainder = remainder.strip()
    default_value: str | None = None
    constraint_section = ""

    default_match = _DEFAULT_PATTERN.search(remainder)
    if default_match:
        data_type_part = remainder[: default_match.start()].strip().rstrip(",")
        after_default = remainder[default_match.end():].strip()
        constraint_match = _CONSTRAINT_PATTERN.search(after_default)
        if constraint_match:
            default_value = after_default[: constraint_match.start()].strip().rstrip(",") or None
            constraint_section = after_default[constraint_match.start():].strip()
        else:
            default_value = after_default.rstrip(",") or None
            constraint_section = ""
    else:
        constraint_match = _CONSTRAINT_PATTERN.search(remainder)
        if constraint_match:
            data_type_part = remainder[: constraint_match.start()].strip().rstrip(",")
            constraint_section = remainder[constraint_match.start():].strip()
        else:
            data_type_part = remainder.rstrip(",")
            constraint_section = ""

    nullable = True
    if re.search(r"\bNOT\s+NULL\b", constraint_section, re.IGNORECASE):
        nullable = False
    elif re.search(r"\bPRIMARY\s+KEY\b", constraint_section, re.IGNORECASE):
        nullable = False
    elif re.search(r"\bNULL\b", constraint_section, re.IGNORECASE):
        nullable = True

    return data_type_part, default_value, nullable


__all__ = [
    "ColumnMetadata",
    "TableMetadata",
    "build_insert_statement",
    "build_mapping_from_files",
    "load_table_metadata",
    "parse_ddl",
]
