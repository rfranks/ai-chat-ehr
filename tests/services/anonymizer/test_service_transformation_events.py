"""Unit tests ensuring anonymizer service accumulates transformation events."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if "presidio_analyzer" not in sys.modules:
    stub = types.ModuleType("presidio_analyzer")

    class AnalyzerEngine:  # pragma: no cover - stub implementation
        def __init__(self, *args, **kwargs) -> None:
            pass

    class RecognizerResult:  # pragma: no cover - stub implementation
        def __init__(self, *args, **kwargs) -> None:
            pass

    class Pattern:  # pragma: no cover - stub implementation
        def __init__(self, *args, **kwargs) -> None:
            pass

    class PatternRecognizer:  # pragma: no cover - stub implementation
        def __init__(self, *args, **kwargs) -> None:
            pass

    stub.AnalyzerEngine = AnalyzerEngine
    stub.RecognizerResult = RecognizerResult
    stub.Pattern = Pattern
    stub.PatternRecognizer = PatternRecognizer
    sys.modules["presidio_analyzer"] = stub

if "pydantic" not in sys.modules:
    pydantic_stub = types.ModuleType("pydantic")

    class BaseModel:  # pragma: no cover - stub implementation
        def __init__(self, **data) -> None:
            for key, value in data.items():
                setattr(self, key, value)

        def model_dump(self, *_, **__) -> dict[str, object]:  # pragma: no cover - stub
            return dict(self.__dict__)

        def model_copy(self, *, deep: bool = False):  # pragma: no cover - stub
            if deep:
                import copy

                return copy.deepcopy(self)
            return self.__class__(**self.model_dump())

    def Field(default=..., **_kwargs):  # pragma: no cover - stub
        return default

    def ConfigDict(**kwargs):  # pragma: no cover - stub
        return dict(kwargs)

    class ValidationError(Exception):  # pragma: no cover - stub
        pass

    pydantic_stub.BaseModel = BaseModel
    pydantic_stub.Field = Field
    pydantic_stub.ConfigDict = ConfigDict
    pydantic_stub.ValidationError = ValidationError
    sys.modules["pydantic"] = pydantic_stub

if "structlog" not in sys.modules:
    structlog_stub = types.ModuleType("structlog")

    class _BoundLogger:
        def __init__(self, *args, **kwargs) -> None:  # pragma: no cover - stub
            pass

        def bind(self, **_kwargs):  # pragma: no cover - stub
            return self

        def info(self, *args, **kwargs):  # pragma: no cover - stub
            return None

        def debug(self, *args, **kwargs):  # pragma: no cover - stub
            return None

    class _LoggerFactory:
        def __call__(self, *args, **kwargs):  # pragma: no cover - stub
            return _BoundLogger()

    class _ContextVarsModule:
        @staticmethod
        def merge_contextvars(*args, **kwargs):  # pragma: no cover - stub
            return {}

        @staticmethod
        def bind_contextvars(*args, **kwargs):  # pragma: no cover - stub
            return None

        @staticmethod
        def get_contextvars():  # pragma: no cover - stub
            return {}

    class _ProcessorsModule:
        @staticmethod
        def add_log_level(logger, method_name, event_dict):  # pragma: no cover - stub
            return event_dict

        class TimeStamper:  # pragma: no cover - stub
            def __init__(self, *args, **kwargs) -> None:
                pass

        class StackInfoRenderer:  # pragma: no cover - stub
            def __call__(self, *args, **kwargs):
                return args[-1] if args else {}

        @staticmethod
        def format_exc_info(*args, **kwargs):  # pragma: no cover - stub
            return {}

        class JSONRenderer:  # pragma: no cover - stub
            def __call__(self, *args, **kwargs):
                return {}

    structlog_stub.contextvars = _ContextVarsModule()
    structlog_stub.processors = _ProcessorsModule()
    structlog_stub.stdlib = types.SimpleNamespace(
        LoggerFactory=_LoggerFactory,
        BoundLogger=_BoundLogger,
    )

    def _configure(*args, **kwargs):  # pragma: no cover - stub
        return None

    def _get_logger(*args, **kwargs):  # pragma: no cover - stub
        return _BoundLogger()

    structlog_stub.configure = _configure
    structlog_stub.get_logger = _get_logger
    sys.modules["structlog"] = structlog_stub

if "loguru" not in sys.modules:
    loguru_stub = types.ModuleType("loguru")

    class _DummyContext:
        def __enter__(self):  # pragma: no cover - stub
            return self

        def __exit__(self, exc_type, exc, tb):  # pragma: no cover - stub
            return False

    class _LoguruLogger:
        def bind(self, **_kwargs):  # pragma: no cover - stub
            return self

        def configure(self, **_kwargs):  # pragma: no cover - stub
            return None

        def remove(self, *args, **kwargs):  # pragma: no cover - stub
            return None

        def add(self, *args, **kwargs):  # pragma: no cover - stub
            return 0

        def contextualize(self, **_kwargs):  # pragma: no cover - stub
            return _DummyContext()

        def level(self, name):  # pragma: no cover - stub
            class _Level:
                def __init__(self, level_name: str) -> None:
                    self.name = level_name

            return _Level(name)

    loguru_stub.logger = _LoguruLogger()
    sys.modules["loguru"] = loguru_stub

if "shared" not in sys.modules:
    shared_stub = types.ModuleType("shared")
    observability_stub = types.ModuleType("shared.observability")
    logger_stub = types.ModuleType("shared.observability.logger")

    class _SharedLogger:
        def info(self, *args, **kwargs):  # pragma: no cover - stub
            return None

        def debug(self, *args, **kwargs):  # pragma: no cover - stub
            return None

        def bind(self, **_kwargs):  # pragma: no cover - stub
            return self

    def _get_shared_logger(_name: str | None = None) -> _SharedLogger:
        return _SharedLogger()

    logger_stub.get_logger = _get_shared_logger

    shared_stub.observability = observability_stub  # type: ignore[attr-defined]
    observability_stub.logger = logger_stub  # type: ignore[attr-defined]

    shared_stub.__path__ = []  # pragma: no cover - mark as package
    observability_stub.__path__ = []  # pragma: no cover - mark as package

    sys.modules["shared"] = shared_stub
    sys.modules["shared.observability"] = observability_stub
    sys.modules["shared.observability.logger"] = logger_stub

from services.anonymizer.models import TransformationEvent
from services.anonymizer.models.firestore import (
    FirestoreAddress,
    FirestoreCoverage,
    FirestoreName,
    FirestorePatientDocument,
)
from services.anonymizer.service import _anonymize_document


class _StubPresidioEngine:
    """Stub anonymizer engine emitting predefined transformation events."""

    def __init__(self, responses: Mapping[str, tuple[str, str, str]]) -> None:
        """Create stub with mapping from input text to anonymization metadata."""

        self._responses = dict(responses)

    def anonymize(self, text: str, *, collect_events: bool = False):  # type: ignore[override]
        record = self._responses.get(text)
        if record is None:
            if collect_events:
                return text, []
            return text

        anonymized, surrogate, entity_type = record
        if not collect_events:
            return anonymized

        event = TransformationEvent(
            entity_type=entity_type,
            action="replace",
            start=0,
            end=len(text),
            surrogate=surrogate,
        )
        return anonymized, [event]


def _build_document() -> FirestorePatientDocument:
    return FirestorePatientDocument(
        name=FirestoreName(first="Alice", last="Smith"),
        coverages=[],
    )


def test_accumulates_name_events_without_leaking_phi() -> None:
    engine = _StubPresidioEngine(
        {
            "Alice": ("anon-first", "token-first", "PATIENT_FIRST_NAME"),
            "Smith": ("anon-last", "token-last", "PATIENT_LAST_NAME"),
        }
    )
    document = _build_document()

    events: list[TransformationEvent] = []
    anonymized = _anonymize_document(engine, document, events)

    assert anonymized.name.first == "anon-first"
    assert anonymized.name.last == "anon-last"
    assert len(events) == 2
    assert {event.entity_type for event in events} == {
        "PATIENT_FIRST_NAME",
        "PATIENT_LAST_NAME",
    }

    originals = {
        "PATIENT_FIRST_NAME": "Alice",
        "PATIENT_LAST_NAME": "Smith",
    }
    for event in events:
        original_value = originals[event.entity_type]
        assert original_value not in event.surrogate
        assert event.surrogate


def test_accumulates_address_events_without_leaking_phi() -> None:
    engine = _StubPresidioEngine(
        {
            "Alice": ("anon-first", "token-first", "PATIENT_FIRST_NAME"),
            "Smith": ("anon-last", "token-last", "PATIENT_LAST_NAME"),
            "123 Main St": ("anon-address", "token-line1", "COVERAGE_ADDRESS_LINE1"),
            "Metropolis": ("anon-city", "token-city", "COVERAGE_ADDRESS_CITY"),
            "10101": ("anon-postal", "token-postal", "COVERAGE_ADDRESS_POSTAL"),
        }
    )
    document = _build_document()
    document.coverages.append(
        FirestoreCoverage(
            address=FirestoreAddress(
                address_line1="123 Main St",
                city="Metropolis",
                postal_code="10101",
            )
        )
    )

    events: list[TransformationEvent] = []
    _anonymize_document(engine, document, events)

    address_entities = {
        "COVERAGE_ADDRESS_LINE1",
        "COVERAGE_ADDRESS_CITY",
        "COVERAGE_ADDRESS_POSTAL",
    }
    captured = {event.entity_type for event in events if event.entity_type in address_entities}
    assert captured == address_entities

    originals = {
        "COVERAGE_ADDRESS_LINE1": "123 Main St",
        "COVERAGE_ADDRESS_CITY": "Metropolis",
        "COVERAGE_ADDRESS_POSTAL": "10101",
    }
    for event in events:
        if event.entity_type in originals:
            assert originals[event.entity_type] not in event.surrogate
            assert event.surrogate


def test_accumulates_coverage_identifier_events_without_leaking_phi() -> None:
    engine = _StubPresidioEngine(
        {
            "Alice": ("anon-first", "token-first", "PATIENT_FIRST_NAME"),
            "Smith": ("anon-last", "token-last", "PATIENT_LAST_NAME"),
            "M-123": ("anon-member", "token-member", "COVERAGE_MEMBER_ID"),
            "PAYER-001": ("anon-payer", "token-payer", "COVERAGE_PAYER_ID"),
            "Acme Health": ("anon-payer-name", "token-payer-name", "COVERAGE_PAYER_NAME"),
        }
    )
    document = _build_document()
    document.coverages.append(
        FirestoreCoverage(
            member_id="M-123",
            payer_id="PAYER-001",
            payer_name="Acme Health",
        )
    )

    events: list[TransformationEvent] = []
    _anonymize_document(engine, document, events)

    identifier_entities = {
        "COVERAGE_MEMBER_ID",
        "COVERAGE_PAYER_ID",
        "COVERAGE_PAYER_NAME",
    }
    captured = {event.entity_type for event in events if event.entity_type in identifier_entities}
    assert captured == identifier_entities

    originals = {
        "COVERAGE_MEMBER_ID": "M-123",
        "COVERAGE_PAYER_ID": "PAYER-001",
        "COVERAGE_PAYER_NAME": "Acme Health",
    }
    for event in events:
        if event.entity_type in originals:
            assert originals[event.entity_type] not in event.surrogate
            assert event.surrogate
