"""Unit tests ensuring anonymizer service accumulates transformation events."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
import hashlib
import hmac
import os
from pathlib import Path
import sys
import types
from unittest.mock import Mock

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

if "dotenv" not in sys.modules:
    dotenv_stub = types.ModuleType("dotenv")

    def load_dotenv(*_args, **_kwargs):  # pragma: no cover - stub implementation
        return None

    dotenv_stub.load_dotenv = load_dotenv
    sys.modules["dotenv"] = dotenv_stub

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

        def warning(self, *args, **kwargs):  # pragma: no cover - stub
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
    FirestoreEHRMetadata,
    FirestoreName,
    FirestorePatientDocument,
)
import services.anonymizer.service as service_module
from services.anonymizer.service import (
    _anonymize_coverage,
    _anonymize_document,
    _extract_address,
    _coerce_uuid,
)
from uuid import NAMESPACE_URL, uuid5


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


class _EchoPresidioEngine:
    """Stub engine that returns the original text without events."""

    def anonymize(self, text: str, *, collect_events: bool = False):  # type: ignore[override]
        if collect_events:
            return text, []
        return text


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
        }
    )
    document = _build_document()
    document.coverages.append(
        FirestoreCoverage(
            address=FirestoreAddress(
                address_line1="123 Main St",
                address_line2="Unit 3",
                city="Metropolis",
                state="CA",
                postal_code="10101",
                country="US",
            )
        )
    )

    events: list[TransformationEvent] = []
    anonymized = _anonymize_document(engine, document, events)

    address_entities = {
        "PATIENT_ADDRESS_STREET",
        "PATIENT_ADDRESS_CITY",
        "PATIENT_ADDRESS_POSTAL_CODE",
    }
    captured = {event.entity_type for event in events if event.entity_type in address_entities}
    assert captured == address_entities

    synthesized_address = anonymized.coverages[0].address
    assert synthesized_address is not None
    assert synthesized_address.address_line1
    assert synthesized_address.address_line1 != "123 Main St"
    assert synthesized_address.city
    assert synthesized_address.city != "Metropolis"
    assert synthesized_address.postal_code
    assert synthesized_address.postal_code != "10101"
    assert synthesized_address.address_line2 == "Unit 3"
    assert synthesized_address.state == "CA"
    assert synthesized_address.country == "US"

    synthesized_events = {
        event.entity_type: event for event in events if event.entity_type in address_entities
    }
    for entity in address_entities:
        event = synthesized_events[entity]
        assert event.surrogate.startswith("Synthesized patient mailing")
        assert event.action == "synthesize"
        assert "123 Main St" not in event.surrogate
        assert "Metropolis" not in event.surrogate
        assert "10101" not in event.surrogate

    assert synthesized_address.address_line1 in synthesized_events["PATIENT_ADDRESS_STREET"].surrogate
    assert synthesized_address.city in synthesized_events["PATIENT_ADDRESS_CITY"].surrogate
    assert (
        synthesized_address.postal_code
        in synthesized_events["PATIENT_ADDRESS_POSTAL_CODE"].surrogate
    )


def test_identifier_fallback_hashes_and_emits_events() -> None:
    engine = _EchoPresidioEngine()
    document = FirestorePatientDocument(
        name=FirestoreName(first="Alice", last="Smith"),
        facility_id="FACILITY-123",
        tenant_id="TENANT-456",
        ehr=FirestoreEHRMetadata(instance_id="INSTANCE-789", patient_id="PATIENT-321"),
        coverages=[FirestoreCoverage(member_id="MEMBER-0001")],
    )

    secret = os.environ.get("ANONYMIZER_IDENTIFIER_HASH_SECRET", "ai-chat-ehr-anonymizer").encode(
        "utf-8"
    )

    def _expected(value: str) -> str:
        return hmac.new(secret, value.encode("utf-8"), hashlib.sha256).hexdigest()

    events: list[TransformationEvent] = []
    anonymized = _anonymize_document(engine, document, events)

    expected_hashes = {
        "FACILITY_ID": _expected("FACILITY-123"),
        "TENANT_ID": _expected("TENANT-456"),
        "EHR_INSTANCE_ID": _expected("INSTANCE-789"),
        "EHR_PATIENT_ID": _expected("PATIENT-321"),
        "INSURANCE_MEMBER_ID": _expected("MEMBER-0001"),
    }

    assert anonymized.facility_id == expected_hashes["FACILITY_ID"]
    assert anonymized.tenant_id == expected_hashes["TENANT_ID"]
    assert anonymized.ehr is not None
    assert anonymized.ehr.instance_id == expected_hashes["EHR_INSTANCE_ID"]
    assert anonymized.ehr.patient_id == expected_hashes["EHR_PATIENT_ID"]
    assert anonymized.coverages[0].member_id == expected_hashes["INSURANCE_MEMBER_ID"]

    captured = {event.entity_type for event in events}
    assert captured == set(expected_hashes)
    for event in events:
        assert event.action == "pseudonymize"
        assert event.surrogate == "Applied HMAC pseudonymization fallback for identifier."

    document_id = "doc-42"
    facility_uuid_first = _coerce_uuid(anonymized.facility_id, fallback=f"facility:{document_id}")
    facility_uuid_second = _coerce_uuid(anonymized.facility_id, fallback=f"facility:{document_id}")
    assert facility_uuid_first == facility_uuid_second
    assert facility_uuid_first == uuid5(NAMESPACE_URL, anonymized.facility_id.strip())

    tenant_uuid_first = _coerce_uuid(anonymized.tenant_id, fallback=f"tenant:{document_id}")
    tenant_uuid_second = _coerce_uuid(anonymized.tenant_id, fallback=f"tenant:{document_id}")
    assert tenant_uuid_first == tenant_uuid_second
    assert tenant_uuid_first == uuid5(NAMESPACE_URL, anonymized.tenant_id.strip())


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


def test_anonymize_coverage_preserves_enumerations() -> None:
    engine = _StubPresidioEngine(
        {
            "M-123": ("anon-member", "token-member", "COVERAGE_MEMBER_ID"),
            "Acme Health": (
                "anon-payer-name",
                "token-payer-name",
                "COVERAGE_PAYER_NAME",
            ),
            "PAYER-001": ("anon-payer-id", "token-payer-id", "COVERAGE_PAYER_ID"),
            "Bob": ("anon-first", "token-first", "COVERAGE_SUBSCRIBER_FIRST_NAME"),
            "Jones": ("anon-last", "token-last", "COVERAGE_SUBSCRIBER_LAST_NAME"),
            "Acme Alt": (
                "anon-alt-payer",
                "token-alt-payer",
                "COVERAGE_ALT_PAYER_NAME",
            ),
        }
    )
    coverage = FirestoreCoverage(
        member_id="M-123",
        payer_name="Acme Health",
        payer_id="PAYER-001",
        first_name="Bob",
        last_name="Jones",
        alt_payer_name="Acme Alt",
        gender="female",
        relationship_to_subscriber="self",
        insurance_type="ppo",
        payer_rank=1,
    )

    events: list[TransformationEvent] = []
    anonymized = _anonymize_coverage(engine, coverage, events)

    assert anonymized.member_id == "anon-member"
    assert anonymized.payer_name == "anon-payer-name"
    assert anonymized.payer_id == "anon-payer-id"
    assert anonymized.first_name == "anon-first"
    assert anonymized.last_name == "anon-last"
    assert anonymized.alt_payer_name == "anon-alt-payer"

    assert anonymized.gender == coverage.gender
    assert anonymized.relationship_to_subscriber == coverage.relationship_to_subscriber
    assert anonymized.insurance_type == coverage.insurance_type
    assert anonymized.payer_rank == coverage.payer_rank

    captured_entities = {event.entity_type for event in events}
    assert captured_entities == {
        "COVERAGE_MEMBER_ID",
        "COVERAGE_PAYER_NAME",
        "COVERAGE_PAYER_ID",
        "COVERAGE_SUBSCRIBER_FIRST_NAME",
        "COVERAGE_SUBSCRIBER_LAST_NAME",
        "COVERAGE_ALT_PAYER_NAME",
    }

    for event in events:
        assert event.surrogate
        assert event.action == "replace"
        assert event.entity_type not in {
            "COVERAGE_GENDER",
            "COVERAGE_RELATIONSHIP",
            "COVERAGE_INSURANCE_TYPE",
            "COVERAGE_PAYER_RANK",
        }


def test_anonymize_coverage_is_deterministic_for_phi_fields() -> None:
    engine = _StubPresidioEngine(
        {
            "M-123": ("anon-member", "token-member", "COVERAGE_MEMBER_ID"),
            "Acme Health": (
                "anon-payer-name",
                "token-payer-name",
                "COVERAGE_PAYER_NAME",
            ),
            "PAYER-001": ("anon-payer-id", "token-payer-id", "COVERAGE_PAYER_ID"),
        }
    )
    coverage = FirestoreCoverage(
        member_id="M-123",
        payer_name="Acme Health",
        payer_id="PAYER-001",
    )

    first_events: list[TransformationEvent] = []
    second_events: list[TransformationEvent] = []

    first = _anonymize_coverage(engine, coverage, first_events)
    second = _anonymize_coverage(engine, coverage, second_events)

    assert first.member_id == second.member_id == "anon-member"
    assert first.payer_name == second.payer_name == "anon-payer-name"
    assert first.payer_id == second.payer_id == "anon-payer-id"

    first_surrogates = {
        (event.entity_type, event.surrogate)
        for event in first_events
        if event.entity_type in {"COVERAGE_MEMBER_ID", "COVERAGE_PAYER_NAME", "COVERAGE_PAYER_ID"}
    }
    second_surrogates = {
        (event.entity_type, event.surrogate)
        for event in second_events
        if event.entity_type in {"COVERAGE_MEMBER_ID", "COVERAGE_PAYER_NAME", "COVERAGE_PAYER_ID"}
    }
    assert first_surrogates == second_surrogates


def test_anonymize_coverage_generalizes_plan_effective_date() -> None:
    engine = _StubPresidioEngine({})
    coverage = FirestoreCoverage(plan_effective_date=date(2015, 4, 1))

    events: list[TransformationEvent] = []
    anonymized = _anonymize_coverage(engine, coverage, events)

    assert anonymized.plan_effective_date == date(2015, 1, 1)

    plan_events = [
        event for event in events if event.entity_type == "COVERAGE_PLAN_EFFECTIVE_DATE"
    ]
    assert len(plan_events) == 1
    plan_event = plan_events[0]
    assert plan_event.action == "generalize"
    assert "2015-01-01" in plan_event.surrogate


def test_anonymize_coverage_logs_malformed_plan_effective_date(monkeypatch) -> None:
    engine = _StubPresidioEngine({})
    coverage = FirestoreCoverage()
    object.__setattr__(coverage, "plan_effective_date", "04/01/2015")

    mock_logger = Mock()
    monkeypatch.setattr(service_module, "logger", mock_logger)

    events: list[TransformationEvent] = []
    anonymized = _anonymize_coverage(engine, coverage, events)

    assert anonymized.plan_effective_date is None
    assert not [
        event for event in events if event.entity_type == "COVERAGE_PLAN_EFFECTIVE_DATE"
    ]

    mock_logger.warning.assert_called_once()
    args, kwargs = mock_logger.warning.call_args
    assert "malformed input" in args[0]
    assert kwargs.get("event") == "anonymizer.coverage.plan_effective_date_invalid"


def test_extract_address_returns_synthesized_fields() -> None:
    engine = _StubPresidioEngine(
        {
            "Alice": ("anon-first", "token-first", "PATIENT_FIRST_NAME"),
            "Smith": ("anon-last", "token-last", "PATIENT_LAST_NAME"),
        }
    )
    document = _build_document()
    document.coverages.append(
        FirestoreCoverage(
            address=FirestoreAddress(
                address_line1="500 Elm Street",
                address_line2="Suite 12",
                city="Oldtown",
                state="TX",
                postal_code="73301",
                country="US",
            )
        )
    )

    anonymized = _anonymize_document(engine, document)
    synthesized_address = anonymized.coverages[0].address
    assert synthesized_address is not None

    generalized = _extract_address(anonymized)

    expected = {
        "street": synthesized_address.address_line1,
        "city": synthesized_address.city,
        "state": synthesized_address.state,
        "postal_code": synthesized_address.postal_code,
        "country": synthesized_address.country,
    }
    if synthesized_address.address_line2:
        expected["unit"] = synthesized_address.address_line2

    assert generalized == expected


def test_extract_address_handles_missing_state() -> None:
    engine = _StubPresidioEngine({})
    document = _build_document()
    document.coverages.append(
        FirestoreCoverage(
            address=FirestoreAddress(
                address_line1="742 Evergreen Terrace",
                city="Springfield",
                postal_code="99999",
                country="US",
            )
        )
    )

    events: list[TransformationEvent] = []
    anonymized = _anonymize_document(engine, document, events)

    synthesized_address = anonymized.coverages[0].address
    assert synthesized_address is not None

    generalized = _extract_address(anonymized)

    expected = {
        "street": synthesized_address.address_line1,
        "city": synthesized_address.city,
        "postal_code": synthesized_address.postal_code,
        "country": synthesized_address.country,
    }
    assert generalized == expected

    synthesized_entities = {
        "PATIENT_ADDRESS_STREET",
        "PATIENT_ADDRESS_CITY",
        "PATIENT_ADDRESS_POSTAL_CODE",
    }
    captured = {event.entity_type for event in events if event.entity_type in synthesized_entities}
    assert captured == synthesized_entities

    synthesized_events = {
        event.entity_type: event for event in events if event.entity_type in synthesized_entities
    }
    for entity in synthesized_entities:
        event = synthesized_events[entity]
        assert event.action == "synthesize"
        assert "742 Evergreen Terrace" not in event.surrogate
        assert "Springfield" not in event.surrogate
        assert "99999" not in event.surrogate

    assert synthesized_address.address_line1 in synthesized_events["PATIENT_ADDRESS_STREET"].surrogate
    assert synthesized_address.city in synthesized_events["PATIENT_ADDRESS_CITY"].surrogate
    assert (
        synthesized_address.postal_code
        in synthesized_events["PATIENT_ADDRESS_POSTAL_CODE"].surrogate
    )
