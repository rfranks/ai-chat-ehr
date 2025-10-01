from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

import structlog

from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.generator.observability import cli_request_context, scrub_for_logging
from shared.observability.logger import get_request_id


@dataclass
class ExampleRecord:
    name: str
    age: int


class ExampleModel(BaseModel):
    payload: dict[str, str]


def test_scrub_for_logging_redacts_strings() -> None:
    payload = {
        "patient": "John Doe",
        "age": 42,
        "notes": ["Sensitive", "Another secret"],
    }

    sanitized = scrub_for_logging(payload)

    assert sanitized["patient"] == "[redacted]"
    assert sanitized["age"] == 42
    assert sanitized["notes"] == ["[redacted]", "[redacted]"]


def test_scrub_for_logging_respects_allowed_keys() -> None:
    payload = {"hint": "SAFE", "secret": "value"}

    sanitized = scrub_for_logging(payload, allow_keys={"hint"})

    assert sanitized["hint"] == "SAFE"
    assert sanitized["secret"] == "[redacted]"


def test_scrub_for_logging_handles_dataclasses_and_models() -> None:
    record = ExampleRecord(name="Alice", age=30)
    model = ExampleModel(payload={"token": "abc123"})

    sanitized_record = scrub_for_logging(record)
    sanitized_model = scrub_for_logging(model)

    assert sanitized_record["name"] == "[redacted]"
    assert sanitized_record["age"] == 30
    assert sanitized_model["payload"]["token"] == "[redacted]"


def test_cli_request_context_binds_request_metadata() -> None:
    with cli_request_context(operation="demo") as request_id:
        assert request_id == get_request_id()
        context = structlog.contextvars.get_contextvars()
        assert context["operation"] == "demo"
        assert context["channel"] == "cli"

    remaining = structlog.contextvars.get_contextvars()
    assert "operation" not in remaining
    assert "channel" not in remaining
