"""Tests for anonymizer logging guardrails."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from uuid import UUID, uuid4
import importlib.util
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PRESIDIO_STUB = types.ModuleType("services.anonymizer.presidio_engine")
PRESIDIO_STUB.AnonymizationAction = type("AnonymizationAction", (), {})  # type: ignore[attr-defined]
PRESIDIO_STUB.EntityAnonymizationRule = type("EntityAnonymizationRule", (), {})  # type: ignore[attr-defined]
PRESIDIO_STUB.PresidioAnonymizerEngine = type("PresidioAnonymizerEngine", (), {})  # type: ignore[attr-defined]
PRESIDIO_STUB.PresidioEngineConfig = type("PresidioEngineConfig", (), {})  # type: ignore[attr-defined]
PRESIDIO_STUB.SAFE_HARBOR_ENTITIES = ()  # type: ignore[attr-defined]
sys.modules.setdefault("services.anonymizer.presidio_engine", PRESIDIO_STUB)

LOGGING_PATH = ROOT / "services" / "anonymizer" / "logging_utils.py"
_SPEC = importlib.util.spec_from_file_location(
    "services.anonymizer.logging_utils", LOGGING_PATH
)
if _SPEC is None or _SPEC.loader is None:  # pragma: no cover - defensive guard
    raise RuntimeError("Unable to load logging utilities module for tests")
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

scrub_for_logging = getattr(_MODULE, "scrub_for_logging")
summarize_patient_document = getattr(_MODULE, "summarize_patient_document")


@dataclass
class DummyRow:
    tenant_id: UUID
    status: str
    name_first: str
    name_last: str


class _BaseModelStub:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def model_dump(self, mode: str = "python") -> dict[str, object]:  # pragma: no cover - simple stub
        return dict(self._payload)


_MODULE.BaseModel = _BaseModelStub  # type: ignore[attr-defined]


def test_scrub_for_logging_redacts_strings() -> None:
    payload = {"first": "Alice", "age": 30, "nested": {"member_id": "abc"}}

    sanitized = scrub_for_logging(payload)

    assert sanitized["first"] == "<redacted>"
    assert sanitized["age"] == 30
    assert sanitized["nested"]["member_id"] == "<redacted>"


def test_scrub_for_logging_allows_opt_in_keys() -> None:
    payload = {"hint": "ok"}

    sanitized = scrub_for_logging(payload, allow_keys={"hint"})

    assert sanitized["hint"] == "ok"


def test_scrub_for_logging_summarizes_sequences() -> None:
    payload = {"coverages": [{"member_id": "1"}, {"member_id": "2"}]}

    sanitized = scrub_for_logging(payload)

    coverages = sanitized["coverages"]
    assert coverages["count"] == 2
    assert coverages["__type__"] == "list"
    assert coverages["sample"][0]["member_id"] == "<redacted>"


def test_scrub_for_logging_handles_dataclasses() -> None:
    record = DummyRow(tenant_id=uuid4(), status="inactive", name_first="Given", name_last="Family")

    sanitized = scrub_for_logging(record)

    assert sanitized["status"] == "inactive"
    assert sanitized["name_first"] == "<redacted>"
    assert sanitized["tenant_id"] == "<redacted>"


def test_scrub_for_logging_handles_base_model_like_objects() -> None:
    class DummyModel(_MODULE.BaseModel):  # type: ignore[misc,valid-type]
        pass

    sanitized = scrub_for_logging(DummyModel({"value": "secret"}))

    assert sanitized["value"] == "<redacted>"


@pytest.mark.parametrize(
    "field",
    ["event", "status", "service"],
)
def test_default_allowed_keys_preserved(field: str) -> None:
    payload = {field: "value"}

    sanitized = scrub_for_logging(payload)

    assert sanitized[field] == "value"


def test_summarize_patient_document_returns_high_level_counts() -> None:
    document = {
        "name": {"first": "Jane", "last": "Doe"},
        "dob": date(1990, 1, 1),
        "gender": "female",
        "coverages": [
            {"member_id": "1111"},
            {"address": {"city": "Seattle"}},
        ],
        "facility_id": "fac-1",
        "tenant_name": "Acme",
    }

    summary = summarize_patient_document(document)

    assert summary["has_dob"] is True
    assert summary["has_gender"] is True
    assert summary["coverage_count"] == 2
    assert summary["coverages_with_member_id"] == 1
    assert summary["coverages_with_address"] == 1
    assert summary["facility_metadata_present"] is True
    assert summary["tenant_metadata_present"] is True
