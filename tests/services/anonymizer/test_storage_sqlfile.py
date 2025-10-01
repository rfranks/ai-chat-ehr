"""Tests for the SQL file storage backend used by the anonymizer."""

# ruff: noqa: E402

from __future__ import annotations

from pathlib import Path
import sys
import types
from uuid import UUID, uuid4

import importlib

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if "dotenv" not in sys.modules:
    dotenv_stub = types.ModuleType("dotenv")

    def _load_dotenv(*_args, **_kwargs):  # pragma: no cover - test stub
        return False

    dotenv_stub.load_dotenv = _load_dotenv
    sys.modules["dotenv"] = dotenv_stub

importlib.import_module("services")

if "services.anonymizer" not in sys.modules:
    anonymizer_pkg = types.ModuleType("services.anonymizer")
    anonymizer_pkg.__path__ = [str(ROOT / "services" / "anonymizer")]  # type: ignore[attr-defined]
    sys.modules["services.anonymizer"] = anonymizer_pkg

if "services.anonymizer.storage" not in sys.modules:
    storage_pkg = types.ModuleType("services.anonymizer.storage")
    storage_pkg.__path__ = [str(ROOT / "services" / "anonymizer" / "storage")]  # type: ignore[attr-defined]
    sys.modules["services.anonymizer.storage"] = storage_pkg

from services.anonymizer.storage.postgres import PatientRow
from services.anonymizer.storage.sqlfile import SQLFileStorage


def test_sql_file_storage_emits_insert_statements(tmp_path) -> None:
    output_file = tmp_path / "patients.sql"
    storage = SQLFileStorage(output_file)

    row = PatientRow(
        tenant_id=uuid4(),
        facility_id=uuid4(),
        name_first="Jane",
        name_last="Doe",
        gender="female",
        status="inactive",
        legal_mailing_address={"city": "Somewhere", "state": "CA"},
    )

    patient_id = storage.insert_patient(row)

    assert isinstance(patient_id, UUID)
    assert output_file.exists()

    contents = output_file.read_text()
    assert contents.startswith(SQLFileStorage.HEADER)
    assert contents.count("INSERT INTO patient") == 1
    assert '"name_first"' in contents
    assert "Somewhere" in contents
    assert "::jsonb" in contents

    second_row = PatientRow(
        tenant_id=uuid4(),
        facility_id=uuid4(),
        name_first="John",
        name_last="Smith",
        gender="male",
        status="inactive",
    )

    storage.insert_patient(second_row)
    contents = output_file.read_text()
    assert contents.count("INSERT INTO patient") == 2
