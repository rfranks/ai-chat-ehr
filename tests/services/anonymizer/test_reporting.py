"""Tests for anonymizer reporting helpers."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REPORTING_PATH = ROOT / "services" / "anonymizer" / "reporting.py"
_SPEC = importlib.util.spec_from_file_location(
    "services.anonymizer.reporting", REPORTING_PATH
)
if _SPEC is None or _SPEC.loader is None:  # pragma: no cover - defensive guard
    raise RuntimeError("Unable to load reporting module for tests")
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
summarize_transformations = getattr(_MODULE, "summarize_transformations")


def test_summarize_transformations_basic() -> None:
    events = [
        {"entity_type": "PERSON", "action": "redact", "original": "John Doe"},
        {"entity_type": "PERSON", "action": "redact", "original": "Jane Doe"},
        {"entity_type": "PHONE_NUMBER", "action": "replace", "original": "555-5555"},
    ]

    summary = summarize_transformations(events)

    assert summary == {
        "total_transformations": 3,
        "actions": {"redact": 2, "replace": 1},
        "entities": {
            "PERSON": {"count": 2, "actions": {"redact": 2}},
            "PHONE_NUMBER": {"count": 1, "actions": {"replace": 1}},
        },
    }

    serialized = json.dumps(summary)
    assert "John Doe" not in serialized
    assert "Jane Doe" not in serialized
    assert "555-5555" not in serialized


@pytest.mark.parametrize(
    "events, expected",
    [
        (
            [
                {"entity": "EMAIL_ADDRESS", "strategy": "synthesize"},
                {"entity_type": "UNKNOWN_TYPE", "action": None},
                "not-a-mapping",
            ],
            {
                "total_transformations": 2,
                "actions": {"synthesize": 1, "unknown": 1},
                "entities": {
                    "EMAIL_ADDRESS": {"count": 1, "actions": {"synthesize": 1}},
                    "UNKNOWN_TYPE": {"count": 1, "actions": {"unknown": 1}},
                },
            },
        ),
        (
            [],
            {
                "total_transformations": 0,
                "actions": {},
                "entities": {},
            },
        ),
    ],
)
def test_summarize_transformations_varied(events, expected) -> None:
    summary = summarize_transformations(events)
    assert summary == expected
    # Ensure the result can be serialized into JSON without errors.
    json.dumps(summary)

