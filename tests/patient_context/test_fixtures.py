import asyncio
import json
from pathlib import Path

import pytest

from repositories import emr


def test_load_patient_fixtures_success(tmp_path: Path) -> None:
    record = {"demographics": {"patientId": "patient-1"}, "encounters": []}
    context = {"demographics": {"patientId": "patient-1"}, "summary": "data"}

    record_path = tmp_path / "patient-1_record.json"
    context_path = tmp_path / "patient-1_context.json"
    record_path.write_text(json.dumps(record), encoding="utf-8")
    context_path.write_text(json.dumps(context), encoding="utf-8")

    fixtures = emr.load_patient_fixtures([record_path, context_path])

    assert fixtures == {
        "patient-1": {
            "record": record,
            "context": context,
        }
    }


def test_load_patient_fixtures_reports_errors(tmp_path: Path) -> None:
    valid_record = {"demographics": {"patientId": "patient-2"}}
    record_path = tmp_path / "patient-2_record.json"
    invalid_context_path = tmp_path / "patient-2_context.json"

    record_path.write_text(json.dumps(valid_record), encoding="utf-8")
    invalid_context_path.write_text("{not-json}", encoding="utf-8")

    with pytest.raises(emr.FixtureLoadError) as exc_info:
        emr.load_patient_fixtures([record_path, invalid_context_path])

    assert "invalid JSON" in str(exc_info.value)
    assert exc_info.value.fixtures == {
        "patient-2": {
            "record": valid_record,
        }
    }


def test_emr_repository_uses_loaded_fixtures() -> None:
    repository = emr.EMRRepository()

    record = asyncio.run(repository.fetch_patient_record("123456"))
    context = asyncio.run(repository.fetch_patient_context("123456"))

    assert record is not None
    assert context is not None
    assert record["demographics"]["patientId"] == "123456"
    assert context["demographics"]["patientId"] == "123456"
