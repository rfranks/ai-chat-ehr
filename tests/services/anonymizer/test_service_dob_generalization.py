from __future__ import annotations

# ruff: noqa: E402

from datetime import date
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

    structlog_stub.get_logger = _LoggerFactory()
    structlog_stub.contextvars = _ContextVarsModule()
    structlog_stub.processors = _ProcessorsModule()
    sys.modules["structlog"] = structlog_stub

if "loguru" not in sys.modules:
    loguru_stub = types.ModuleType("loguru")

    class _Logger:  # pragma: no cover - stub implementation
        def bind(self, **_kwargs):
            return self

        def opt(self, **_kwargs):
            return self

        def info(self, *args, **kwargs):
            return None

        def warning(self, *args, **kwargs):
            return None

        def error(self, *args, **kwargs):
            return None

    loguru_stub.logger = _Logger()
    sys.modules["loguru"] = loguru_stub

if "dotenv" not in sys.modules:
    dotenv_stub = types.ModuleType("dotenv")

    def _load_dotenv(*args, **kwargs):  # pragma: no cover - stub implementation
        return None

    dotenv_stub.load_dotenv = _load_dotenv
    sys.modules["dotenv"] = dotenv_stub

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

from services.anonymizer.models.firestore import FirestoreName, FirestorePatientDocument
from services.anonymizer.models.transformation_event import TransformationEvent
from services.anonymizer.service import _convert_to_patient_row


def _build_document(dob: date | None) -> FirestorePatientDocument:
    return FirestorePatientDocument(
        name=FirestoreName(first="Alice", last="Smith"),
        dob=dob,
        gender="Female",
        coverages=[],
    )


def test_generalizes_birth_date_for_patients_younger_than_90() -> None:
    today = date.today()
    dob = date(today.year - 40, 6, 15)
    events = []

    row = _convert_to_patient_row(
        original=_build_document(dob),
        anonymized=_build_document(dob),
        document_id="doc-1",
        event_accumulator=events,
    )

    assert row.dob == date(dob.year, 1, 1)
    assert any(
        event.action == "generalize" and event.entity_type == "PATIENT_DOB"
        for event in events
    )


def test_suppresses_birth_date_for_patients_aged_90_or_older() -> None:
    today = date.today()
    dob = date(today.year - 95, 1, 1)
    events = []

    row = _convert_to_patient_row(
        original=_build_document(dob),
        anonymized=_build_document(dob),
        document_id="doc-2",
        event_accumulator=events,
    )

    assert row.dob is None
    assert any(
        event.action == "suppress" and event.entity_type == "PATIENT_DOB"
        for event in events
    )


def test_patient_row_generalizes_year_only_for_age_eighty_nine() -> None:
    today = date.today()
    dob = date(today.year - 89, 6, 15)
    events: list[TransformationEvent] = []

    row = _convert_to_patient_row(
        original=_build_document(dob),
        anonymized=_build_document(dob),
        document_id="doc-3",
        event_accumulator=events,
    )

    assert row.dob == date(dob.year, 1, 1)
    assert {event.action for event in events} == {"generalize"}
    assert {event.entity_type for event in events} == {"PATIENT_DOB"}
    assert all(dob.isoformat() not in (event.surrogate or "") for event in events)


def test_patient_row_suppresses_dob_for_age_ninety_or_older() -> None:
    today = date.today()
    dob = date(today.year - 90, 1, 1)
    events: list[TransformationEvent] = []

    row = _convert_to_patient_row(
        original=_build_document(dob),
        anonymized=_build_document(dob),
        document_id="doc-4",
        event_accumulator=events,
    )

    assert row.dob is None
    assert {event.action for event in events} == {"suppress"}
    assert {event.entity_type for event in events} == {"PATIENT_DOB"}
    assert all(dob.isoformat() not in (event.surrogate or "") for event in events)


def test_patient_row_generalizes_leap_year_birthdays() -> None:
    dob = date(2000, 2, 29)
    events: list[TransformationEvent] = []

    row = _convert_to_patient_row(
        original=_build_document(dob),
        anonymized=_build_document(dob),
        document_id="doc-5",
        event_accumulator=events,
    )

    assert row.dob == date(2000, 1, 1)
    assert any(event.action == "generalize" for event in events)
    assert {event.entity_type for event in events} == {"PATIENT_DOB"}
    assert all(dob.isoformat() not in (event.surrogate or "") for event in events)


def test_patient_row_handles_missing_birth_date() -> None:
    events: list[TransformationEvent] = []

    row = _convert_to_patient_row(
        original=_build_document(None),
        anonymized=_build_document(None),
        document_id="doc-6",
        event_accumulator=events,
    )

    assert row.dob is None
    assert events == []
