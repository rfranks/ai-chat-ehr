"""Unit tests for the Presidio anonymizer engine."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if "pydantic" not in sys.modules:
    pydantic_stub = types.ModuleType("pydantic")

    class BaseModel:  # pragma: no cover - stub implementation
        def __init__(self, **data) -> None:
            for key, value in data.items():
                setattr(self, key, value)

        def model_dump(self, *_, **__) -> dict[str, object]:
            return dict(self.__dict__)

    def Field(default=..., **_kwargs):  # pragma: no cover - stub
        return default

    def ConfigDict(**kwargs):  # pragma: no cover - stub
        return dict(kwargs)

    pydantic_stub.BaseModel = BaseModel
    pydantic_stub.Field = Field
    pydantic_stub.ConfigDict = ConfigDict
    sys.modules["pydantic"] = pydantic_stub

if "presidio_analyzer" not in sys.modules:
    stub = types.ModuleType("presidio_analyzer")

    class AnalyzerEngine:  # type: ignore[too-many-ancestors]
        def __init__(self, *args, **kwargs) -> None:  # pragma: no cover - stub
            pass

        def analyze(self, *args, **kwargs):  # pragma: no cover - stub
            return []

        @property
        def registry(self):  # pragma: no cover - stub
            class _Registry:
                def add_recognizer(self, *args, **kwargs) -> None:
                    return None

            return _Registry()

    class RecognizerResult:  # pragma: no cover - stub
        def __init__(self, entity_type: str, start: int, end: int, score: float, **_: object) -> None:
            self.entity_type = entity_type
            self.start = start
            self.end = end
            self.score = score

    class Pattern:  # pragma: no cover - stub
        def __init__(self, *args, **kwargs) -> None:
            pass

    class PatternRecognizer:  # pragma: no cover - stub
        def __init__(self, *args, **kwargs) -> None:
            pass

    stub.AnalyzerEngine = AnalyzerEngine
    stub.RecognizerResult = RecognizerResult
    stub.Pattern = Pattern
    stub.PatternRecognizer = PatternRecognizer
    sys.modules["presidio_analyzer"] = stub

from services.anonymizer.models import TransformationEvent
from services.anonymizer.presidio_engine import (
    AnonymizationAction,
    EntityAnonymizationRule,
    PresidioAnonymizerEngine,
    PresidioEngineConfig,
)


@dataclass(slots=True)
class _RecognizerResult:
    entity_type: str
    start: int
    end: int
    score: float = 0.85


class StubAnalyzer:
    """Simple analyzer returning predefined recognizer results."""

    def __init__(self, results: Iterable[_RecognizerResult]) -> None:
        self._results = list(results)

    def analyze(self, *, text: str, language: str) -> list[_RecognizerResult]:  # type: ignore[override]
        return list(self._results)


def _recognizer_result(entity: str, start: int, end: int) -> _RecognizerResult:
    return _RecognizerResult(entity_type=entity, start=start, end=end)


def test_anonymize_returns_string_by_default() -> None:
    text = "Patient John Smith called 212-555-1234 yesterday."
    results = [
        _recognizer_result("PERSON", 8, 18),
        _recognizer_result("PHONE_NUMBER", 26, 38),
    ]
    engine = PresidioAnonymizerEngine(analyzer=StubAnalyzer(results))

    anonymized = engine.anonymize(text)

    assert isinstance(anonymized, str)
    assert "John" not in anonymized
    assert "212-555-1234" not in anonymized


def test_collect_events_emits_surrogate_previews_without_phi() -> None:
    text = "Contact John Smith at 212-555-1234."
    results = [
        _recognizer_result("PERSON", 8, 18),
        _recognizer_result("PHONE_NUMBER", 22, 34),
    ]
    engine = PresidioAnonymizerEngine(analyzer=StubAnalyzer(results))

    anonymized, events = engine.anonymize(text, collect_events=True)

    assert isinstance(anonymized, str)
    assert isinstance(events, list)
    assert all(isinstance(event, TransformationEvent) for event in events)
    assert {event.entity_type for event in events} == {"PERSON", "PHONE_NUMBER"}

    for event, result in zip(events, results):
        original = text[result.start : result.end]
        assert original not in event.surrogate
        assert event.surrogate != original
        assert event.surrogate


def test_redaction_events_mask_values() -> None:
    text = "Patient Jane Doe visited."
    results = [_recognizer_result("PERSON", 8, 16)]
    config = PresidioEngineConfig(
        entity_policies={
            "PERSON": EntityAnonymizationRule(
                action=AnonymizationAction.REDACT,
                replacement="[[MASKED]]",
            )
        }
    )
    engine = PresidioAnonymizerEngine(analyzer=StubAnalyzer(results), config=config)

    anonymized, events = engine.anonymize(text, collect_events=True)

    assert isinstance(anonymized, str)
    assert events[0].surrogate == "[[MASKED]]"
    assert "Jane" not in events[0].surrogate


@pytest.mark.parametrize(
    "surrogate",
    [
        "anon_1234567890abcdef1234567890abcdef",
        "[REDACTED]",
    ],
)
def test_preview_truncates_long_surrogates(surrogate: str) -> None:
    preview = PresidioAnonymizerEngine._preview_surrogate(surrogate)
    assert len(preview) <= 32
    assert preview.startswith(surrogate[: min(len(surrogate), 31)])
    if len(surrogate) > 32:
        assert preview.endswith("…")
    else:
        assert preview == surrogate
