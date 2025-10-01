from __future__ import annotations

import json
from typing import Iterable
from uuid import UUID, uuid4

import pytest

from scripts import run_anonymizer
from services.anonymizer.models import TransformationEvent


class _StubStorage:
    instances: list["_StubStorage"] = []

    def __init__(self, dsn: str, *, bootstrap_schema: bool) -> None:  # type: ignore[override]
        self.dsn = dsn
        self.bootstrap_schema = bootstrap_schema
        self.closed = False
        type(self).instances.append(self)

    def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def _reset_storage_instances() -> Iterable[None]:
    _StubStorage.instances.clear()
    yield
    _StubStorage.instances.clear()


def _install_stubs(monkeypatch: pytest.MonkeyPatch, *, patient_id: UUID, events: list[TransformationEvent]) -> None:
    async def _fake_process_patient(
        collection: str,
        document_id: str,
        *,
        firestore,
        anonymizer,
        storage,
    ):
        # ensure the fixture data source can locate the bundled patient record
        fixture_payload = firestore.get_patient(collection, document_id)
        assert fixture_payload is not None
        assert storage.dsn == "postgresql://anonymizer"
        return patient_id, events

    monkeypatch.setattr(run_anonymizer, "PostgresStorage", _StubStorage)
    monkeypatch.setattr(run_anonymizer, "process_patient", _fake_process_patient)


def test_main_processes_fixture_and_prints_summary(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    patient_id = uuid4()
    events = [
        TransformationEvent(entity_type="NAME", action="replace", start=0, end=4, surrogate="HASHED"),
        TransformationEvent(entity_type="PHONE", action="redact", start=10, end=21, surrogate="***"),
    ]

    _install_stubs(monkeypatch, patient_id=patient_id, events=events)

    exit_code = run_anonymizer.main(
        [
            "patients",
            "xpF51IBED5TOKMPJamWo",
            "--postgres-dsn",
            "postgresql://anonymizer",
            "--dump-summary",
            "--no-bootstrap-schema",
        ]
    )

    assert exit_code == 0

    captured = capsys.readouterr().out.splitlines()
    assert any(str(patient_id) in line for line in captured)
    assert any("Transformation summary:" in line for line in captured)

    summary_json = "\n".join(line for line in captured if line and line.strip().startswith("{"))
    summary = json.loads(summary_json)
    assert summary["total_transformations"] == len(events)
    assert "NAME" in summary["entities"]
    assert "PHONE" in summary["entities"]

    assert _StubStorage.instances and _StubStorage.instances[0].bootstrap_schema is False
    assert _StubStorage.instances[0].closed is True


def test_main_bootstraps_schema_by_default(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    patient_id = uuid4()
    events: list[TransformationEvent] = []

    _install_stubs(monkeypatch, patient_id=patient_id, events=events)

    exit_code = run_anonymizer.main(
        [
            "xpF51IBED5TOKMPJamWo",
            "--postgres-dsn",
            "postgresql://anonymizer",
        ]
    )

    assert exit_code == 0

    assert _StubStorage.instances and _StubStorage.instances[0].bootstrap_schema is True
    assert _StubStorage.instances[0].closed is True

    captured = capsys.readouterr()
    assert str(patient_id) in captured.out
