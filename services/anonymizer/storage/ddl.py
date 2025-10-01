"""Utilities for loading anonymizer DDL statements."""

from __future__ import annotations

from pathlib import Path
from typing import List


DEFAULT_ENCODING = "utf-8"
DDL_DIRECTORY = Path(__file__).resolve().parent.parent / "ddls"


class DDLNotFoundError(FileNotFoundError):
    """Raised when a requested DDL file cannot be located."""


def _ensure_extension(filename: str) -> str:
    """Return *filename* with a ``.ddl`` suffix if it is missing."""

    if not filename.lower().endswith(".ddl"):
        return f"{filename}.ddl"
    return filename


def _load_text(path: Path, encoding: str = DEFAULT_ENCODING) -> str:
    """Read ``path`` with ``encoding`` and return the file contents.

    Parameters
    ----------
    path:
        The file path to load.
    encoding:
        Encoding to use while reading the file.

    Raises
    ------
    DDLNotFoundError
        If ``path`` does not exist.
    UnicodeDecodeError
        If ``encoding`` cannot decode the file contents.
    """

    if not path.exists():
        raise DDLNotFoundError(f"DDL file not found: {path}")

    return path.read_text(encoding=encoding)


def load_ddl(name: str, *, directory: Path = DDL_DIRECTORY, encoding: str = DEFAULT_ENCODING) -> str:
    """Load a DDL file from disk and return its raw contents.

    ``name`` may be provided with or without the ``.ddl`` suffix. ``directory``
    defaults to the anonymizer DDL folder but can be overridden for testing.
    """

    path = directory / _ensure_extension(name)
    return _load_text(path, encoding=encoding)


def parse_statements(ddl_text: str) -> List[str]:
    """Split DDL text into individual SQL statements.

    Comments and empty lines are removed. Statements are returned with their
    trailing semicolons preserved to allow direct execution downstream.
    """

    statements: List[str] = []
    buffer: List[str] = []

    for line in ddl_text.splitlines():
        stripped = line.strip()

        if not stripped or stripped.startswith("--"):
            continue

        buffer.append(line)
        if stripped.endswith(";"):
            statement = "\n".join(buffer).strip()
            statements.append(statement)
            buffer.clear()

    # Capture any trailing statement that may omit a semicolon.
    if buffer:
        statements.append("\n".join(buffer).strip())

    return statements


def load_statements(name: str, *, directory: Path = DDL_DIRECTORY, encoding: str = DEFAULT_ENCODING) -> List[str]:
    """Convenience helper that loads and parses statements from ``name``."""

    ddl_text = load_ddl(name, directory=directory, encoding=encoding)
    return parse_statements(ddl_text)


__all__ = [
    "DDLNotFoundError",
    "DDL_DIRECTORY",
    "load_ddl",
    "load_statements",
    "parse_statements",
]
