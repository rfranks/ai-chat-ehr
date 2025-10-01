"""FastAPI route tests for the anonymizer service."""

# ruff: noqa: E402

from __future__ import annotations

import abc
import asyncio
import json
import sys
import types
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from uuid import UUID, uuid4

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


if "dotenv" not in sys.modules:
    dotenv_stub = types.ModuleType("dotenv")

    def load_dotenv(
        *_args: Any, **_kwargs: Any
    ) -> None:  # pragma: no cover - stub helper
        return None

    dotenv_stub.load_dotenv = load_dotenv
    sys.modules["dotenv"] = dotenv_stub


# ---------------------------------------------------------------------------
# Dependency stubs
# ---------------------------------------------------------------------------


class _FieldInfo:
    __slots__ = ("default", "alias", "default_factory")

    def __init__(
        self,
        default: Any = ...,
        *,
        alias: str | None = None,
        default_factory: Callable[[], Any] | None = None,
        **_kwargs: Any,
    ) -> None:
        self.default = default
        self.alias = alias
        self.default_factory = default_factory


if "pydantic" not in sys.modules:

    class _BaseModelMeta(abc.ABCMeta):
        def __new__(mcls, name, bases, namespace, **kwargs):
            annotations: dict[str, Any] = {}
            for base in reversed(bases):
                annotations.update(getattr(base, "__annotations__", {}))
            annotations.update(namespace.get("__annotations__", {}))

            field_metadata: dict[str, _FieldInfo] = {}
            alias_map: dict[str, str] = {}

            for field_name in annotations:
                if field_name.startswith("_"):
                    continue
                value = namespace.get(field_name, ...)
                if isinstance(value, _FieldInfo):
                    info = value
                    namespace.pop(field_name, None)
                else:
                    if field_name in namespace:
                        default_value = namespace.pop(field_name)
                    else:
                        default_value = ...
                    info = _FieldInfo(default=default_value)
                alias = info.alias or field_name
                info.alias = alias
                field_metadata[field_name] = info
                alias_map[field_name] = alias

            namespace["_field_metadata"] = field_metadata
            namespace["_field_aliases"] = alias_map
            return super().__new__(mcls, name, bases, namespace)

    def _serialize(value: Any, *, by_alias: bool, exclude_none: bool):
        if isinstance(value, _BaseModel):  # type: ignore[name-defined]
            return value.model_dump(by_alias=by_alias, exclude_none=exclude_none)
        if isinstance(value, list):
            return [
                _serialize(item, by_alias=by_alias, exclude_none=exclude_none)
                for item in value
            ]
        if isinstance(value, dict):
            return {
                key: _serialize(val, by_alias=by_alias, exclude_none=exclude_none)
                for key, val in value.items()
            }
        return value

    class _BaseModel(Mapping, metaclass=_BaseModelMeta):
        _field_metadata: dict[str, _FieldInfo]
        _field_aliases: dict[str, str]

        def __init__(self, **data: Any) -> None:
            values: dict[str, Any] = {}
            extras: dict[str, Any] = {}
            for key, value in data.items():
                matched: str | None = None
                for field_name, alias in self._field_aliases.items():
                    if key == field_name or key == alias:
                        matched = field_name
                        break
                if matched is None:
                    extras[key] = value
                else:
                    values[matched] = value

            for field_name, info in self._field_metadata.items():
                if field_name in values:
                    value = values[field_name]
                else:
                    if info.default is not ...:
                        value = info.default
                    elif info.default_factory is not None:
                        value = info.default_factory()
                    else:
                        raise _ValidationError(f"Missing field '{field_name}'")
                setattr(self, field_name, value)

            for key, value in extras.items():
                setattr(self, key, value)

        def __getitem__(self, item: str) -> Any:
            return getattr(self, item)

        def __iter__(self):
            return iter(self._field_aliases.keys())

        def __len__(self) -> int:
            return len(self._field_aliases)

        def model_dump(
            self,
            *,
            by_alias: bool = False,
            exclude_none: bool = False,
            mode: str | None = None,
        ) -> dict[str, Any]:
            payload: dict[str, Any] = {}
            for field_name, info in self._field_metadata.items():
                key = info.alias if by_alias else field_name
                value = getattr(self, field_name)
                if exclude_none and value is None:
                    continue
                payload[key] = _serialize(
                    value, by_alias=by_alias, exclude_none=exclude_none
                )
            for key, value in self.__dict__.items():
                if key in self._field_metadata:
                    continue
                if exclude_none and value is None:
                    continue
                payload[key] = _serialize(
                    value, by_alias=by_alias, exclude_none=exclude_none
                )
            return payload

        @classmethod
        def model_validate(cls, data: Any):
            if isinstance(data, cls):
                return data
            if isinstance(data, Mapping):
                return cls(**data)
            raise _ValidationError("Invalid data for model validation")

        def model_copy(self, *, deep: bool = False):
            if deep:
                import copy

                return copy.deepcopy(self)
            return self.__class__(**self.model_dump())

    class _ValidationError(Exception):
        pass

    def _config_dict(**kwargs: Any) -> dict[str, Any]:
        return dict(kwargs)

    pydantic_stub = types.ModuleType("pydantic")
    pydantic_stub.BaseModel = _BaseModel
    pydantic_stub.Field = lambda *args, **kwargs: _FieldInfo(*args, **kwargs)
    pydantic_stub.ConfigDict = _config_dict
    pydantic_stub.ValidationError = _ValidationError
    sys.modules["pydantic"] = pydantic_stub

if "presidio_analyzer" not in sys.modules:
    presidio_stub = types.ModuleType("presidio_analyzer")

    class _AnalyzerEngine:  # pragma: no cover - stub behavior
        pass

    class _RecognizerResult:  # pragma: no cover - stub behavior
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.entity_type = "PERSON"
            self.start = 0
            self.end = 0

    class _Pattern:  # pragma: no cover - stub behavior
        pass

    class _PatternRecognizer:  # pragma: no cover - stub behavior
        pass

    presidio_stub.AnalyzerEngine = _AnalyzerEngine
    presidio_stub.RecognizerResult = _RecognizerResult
    presidio_stub.Pattern = _Pattern
    presidio_stub.PatternRecognizer = _PatternRecognizer
    sys.modules["presidio_analyzer"] = presidio_stub

if "structlog" not in sys.modules:
    structlog_stub = types.ModuleType("structlog")

    class _BoundLogger:  # pragma: no cover - stub behavior
        def bind(self, **_kwargs: Any) -> "_BoundLogger":
            return self

        def info(self, *args: Any, **kwargs: Any) -> None:
            return None

        def debug(self, *args: Any, **kwargs: Any) -> None:
            return None

        def exception(self, *args: Any, **kwargs: Any) -> None:
            return None

    class _LoggerFactory:  # pragma: no cover - stub behavior
        def __call__(self, *args: Any, **kwargs: Any) -> _BoundLogger:
            return _BoundLogger()

    class _ContextVarsModule:  # pragma: no cover - stub behavior
        @staticmethod
        def merge_contextvars(*args: Any, **kwargs: Any) -> dict[str, Any]:
            return {}

        @staticmethod
        def bind_contextvars(*args: Any, **kwargs: Any) -> None:
            return None

        @staticmethod
        def get_contextvars() -> dict[str, Any]:
            return {}

    class _ProcessorsModule:  # pragma: no cover - stub behavior
        @staticmethod
        def add_log_level(
            logger: Any, method_name: str, event_dict: dict[str, Any]
        ) -> dict[str, Any]:
            return event_dict

        class TimeStamper:  # pragma: no cover - stub behavior
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                pass

        class StackInfoRenderer:  # pragma: no cover - stub behavior
            def __call__(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
                return {}

        @staticmethod
        def format_exc_info(*args: Any, **kwargs: Any) -> dict[str, Any]:
            return {}

        class JSONRenderer:  # pragma: no cover - stub behavior
            def __call__(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
                return {}

    structlog_stub.contextvars = _ContextVarsModule()
    structlog_stub.processors = _ProcessorsModule()
    structlog_stub.stdlib = types.SimpleNamespace(
        LoggerFactory=_LoggerFactory,
        BoundLogger=_BoundLogger,
    )

    def _configure(
        *args: Any, **kwargs: Any
    ) -> None:  # pragma: no cover - stub behavior
        return None

    def _get_logger(
        *args: Any, **kwargs: Any
    ) -> _BoundLogger:  # pragma: no cover - stub behavior
        return _BoundLogger()

    structlog_stub.configure = _configure
    structlog_stub.get_logger = _get_logger
    sys.modules["structlog"] = structlog_stub

if "loguru" not in sys.modules:
    loguru_stub = types.ModuleType("loguru")

    class _DummyContext:  # pragma: no cover - stub behavior
        def __enter__(self) -> "_DummyContext":
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
            return False

    class _LoguruLogger:  # pragma: no cover - stub behavior
        def bind(self, **_kwargs: Any) -> "_LoguruLogger":
            return self

        def configure(self, **_kwargs: Any) -> None:
            return None

        def remove(self, *args: Any, **kwargs: Any) -> None:
            return None

        def add(self, *args: Any, **kwargs: Any) -> int:
            return 0

        def contextualize(self, **_kwargs: Any) -> _DummyContext:
            return _DummyContext()

        def opt(self, *args: Any, **kwargs: Any) -> "_LoguruLogger":
            return self

        def level(self, name: str):  # pragma: no cover - stub behavior
            class _Level:
                def __init__(self, level_name: str) -> None:
                    self.name = level_name

            return _Level(name)

        def log(self, *args: Any, **kwargs: Any) -> None:
            return None

        def exception(self, *args: Any, **kwargs: Any) -> None:
            return None

    loguru_stub.logger = _LoguruLogger()
    sys.modules["loguru"] = loguru_stub

if "fastapi" not in sys.modules:
    fastapi_stub = types.ModuleType("fastapi")
    fastapi_stub.__path__ = []  # pragma: no cover - mark as package

    status = types.SimpleNamespace(
        HTTP_200_OK=200,
        HTTP_202_ACCEPTED=202,
        HTTP_404_NOT_FOUND=404,
        HTTP_409_CONFLICT=409,
        HTTP_422_UNPROCESSABLE_ENTITY=422,
        HTTP_500_INTERNAL_SERVER_ERROR=500,
        HTTP_502_BAD_GATEWAY=502,
        HTTP_503_SERVICE_UNAVAILABLE=503,
    )

    class _HTTPException(Exception):  # pragma: no cover - stub behavior
        def __init__(self, status_code: int, detail: str | None = None) -> None:
            self.status_code = status_code
            self.detail = detail
            super().__init__(detail)

    class _Request:  # pragma: no cover - stub behavior
        def __init__(
            self, url: str = "http://test", path_params: dict[str, Any] | None = None
        ) -> None:
            self.url = types.SimpleNamespace(__str__=lambda self_ref: url, path="/")
            self.path_params = path_params or {}

    class _FastAPI:  # pragma: no cover - stub behavior
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.exception_handlers: dict[type[BaseException], Callable[..., Any]] = {}

        def add_middleware(self, *args: Any, **kwargs: Any) -> None:
            return None

        def include_router(self, _router: Any) -> None:
            return None

        def exception_handler(self, exc_type: type[BaseException]):
            def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                self.exception_handlers[exc_type] = func
                return func

            return decorator

        def add_exception_handler(
            self,
            exc_type: type[BaseException],
            handler: Callable[..., Any],
        ) -> None:
            self.exception_handlers[exc_type] = handler

        def get(self, _path: str, **_kwargs: Any):
            def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                return func

            return decorator

    class _APIRouter:  # pragma: no cover - stub behavior
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def post(self, _path: str, **_kwargs: Any):
            def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                return func

            return decorator

        def get(self, _path: str, **_kwargs: Any):
            def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                return func

            return decorator

    def _path(default: Any, **_kwargs: Any) -> Any:  # pragma: no cover - stub behavior
        return default

    fastapi_stub.FastAPI = _FastAPI
    fastapi_stub.APIRouter = _APIRouter
    fastapi_stub.HTTPException = _HTTPException
    fastapi_stub.Request = _Request
    fastapi_stub.Path = _path
    fastapi_stub.status = status
    sys.modules["fastapi"] = fastapi_stub

    exceptions_stub = types.ModuleType("fastapi.exceptions")

    class _RequestValidationError(Exception):  # pragma: no cover - stub behavior
        pass

    exceptions_stub.RequestValidationError = _RequestValidationError
    sys.modules["fastapi.exceptions"] = exceptions_stub

    responses_stub = types.ModuleType("fastapi.responses")

    class _JSONResponse:  # pragma: no cover - stub behavior
        def __init__(self, content: Any, status_code: int = 200) -> None:
            self.content = content
            self.status_code = status_code
            self.body = content

    responses_stub.JSONResponse = _JSONResponse
    sys.modules["fastapi.responses"] = responses_stub

if "starlette" not in sys.modules:
    starlette_stub = types.ModuleType("starlette")
    starlette_stub.__path__ = []  # pragma: no cover - mark as package
    sys.modules["starlette"] = starlette_stub

    middleware_pkg = types.ModuleType("starlette.middleware")
    middleware_pkg.__path__ = []  # pragma: no cover - mark as package
    sys.modules["starlette.middleware"] = middleware_pkg

    base_module = types.ModuleType("starlette.middleware.base")

    class _BaseHTTPMiddleware:  # pragma: no cover - stub behavior
        def __init__(self, app: Any) -> None:
            self.app = app

    base_module.BaseHTTPMiddleware = _BaseHTTPMiddleware
    sys.modules["starlette.middleware.base"] = base_module

    requests_module = types.ModuleType("starlette.requests")

    class _StarletteRequest:  # pragma: no cover - stub behavior
        def __init__(self) -> None:
            self.headers: dict[str, str] = {}
            self.state = types.SimpleNamespace()
            self.client = types.SimpleNamespace(host=None)
            self.url = types.SimpleNamespace(
                path="/", __str__=lambda self_ref: "http://test"
            )
            self.method = "GET"
            self.scope: dict[str, Any] = {}

    requests_module.Request = _StarletteRequest
    sys.modules["starlette.requests"] = requests_module

    responses_module = types.ModuleType("starlette.responses")

    class _StarletteResponse:  # pragma: no cover - stub behavior
        def __init__(self) -> None:
            self.headers: dict[str, str] = {}

    responses_module.Response = _StarletteResponse
    sys.modules["starlette.responses"] = responses_module

    types_module = types.ModuleType("starlette.types")
    types_module.ASGIApp = object  # pragma: no cover - stub behavior
    sys.modules["starlette.types"] = types_module

    exceptions_module = types.ModuleType("starlette.exceptions")

    class _StarletteHTTPException(Exception):  # pragma: no cover - stub behavior
        def __init__(self, status_code: int, detail: str | None = None) -> None:
            self.status_code = status_code
            self.detail = detail
            super().__init__(detail)

    exceptions_module.HTTPException = _StarletteHTTPException
    sys.modules["starlette.exceptions"] = exceptions_module

from services.anonymizer.models import TransformationEvent
import services.anonymizer.app as app_module
import services.anonymizer.service as service_module
from services.anonymizer.firestore.client import FirestoreDataSource
from services.anonymizer.storage.postgres import (
    PatientRow as StoragePatientRow,
    StorageError,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


@dataclass
class _StubRequest:
    """Minimal request object used to exercise exception handlers."""

    url: str
    path_params: dict[str, str]

    def __post_init__(self) -> None:
        value = self.url
        self.url = types.SimpleNamespace(__str__=lambda _self: value, path=value)


@pytest.fixture
def transformation_events() -> list[TransformationEvent]:
    """Return deterministic transformation events used by the happy path test."""

    return [
        TransformationEvent(
            entity_type="PERSON",
            action="replace",
            start=0,
            end=5,
            surrogate="anon-first",
        ),
        TransformationEvent(
            entity_type="PERSON",
            action="replace",
            start=6,
            end=11,
            surrogate="anon-last",
        ),
        TransformationEvent(
            entity_type="ACCOUNT_NUMBER",
            action="redact",
            start=12,
            end=20,
            surrogate="token-account",
        ),
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_anonymize_document_returns_summary(
    monkeypatch: pytest.MonkeyPatch,
    transformation_events: list[TransformationEvent],
) -> None:
    """anonymize_document should return the structured response model."""

    patient_id = uuid4()
    raw_phi = {"Alice Example", "MRN-12345"}

    async def _fake_process_patient(
        collection: str, document_id: str
    ) -> tuple[UUID, list[TransformationEvent]]:
        assert collection == "patients"
        assert document_id == "phi-12345"
        return patient_id, transformation_events

    monkeypatch.setattr(app_module, "process_patient", _fake_process_patient)

    response = asyncio.run(app_module.anonymize_document("patients", "phi-12345"))

    assert isinstance(response, app_module.AnonymizeResponse)
    payload = response.model_dump(by_alias=True)
    assert payload["status"] == "accepted"

    summary = payload["summary"]
    assert str(summary["recordId"]) == str(patient_id)

    aggregates = summary["transformations"]
    assert aggregates["total_transformations"] == len(transformation_events)
    assert aggregates["actions"] == {"redact": 1, "replace": 2}
    assert aggregates["entities"] == {
        "ACCOUNT_NUMBER": {"count": 1, "actions": {"redact": 1}},
        "PERSON": {"count": 2, "actions": {"replace": 2}},
    }

    serialized = json.dumps(payload, default=str)
    for token in raw_phi:
        assert token not in serialized


@pytest.mark.parametrize(
    "exception_cls, exception_kwargs, handler, status_code, type_suffix, expected_processing_error",
    [
        (
            app_module.PatientNotFoundError,
            {},
            app_module.handle_patient_not_found,
            app_module.status.HTTP_404_NOT_FOUND,
            "patient-not-found",
            None,
        ),
        (
            app_module.DuplicatePatientError,
            {},
            app_module.handle_duplicate_patient,
            app_module.status.HTTP_409_CONFLICT,
            "duplicate-patient",
            None,
        ),
        (
            app_module.PatientProcessingError,
            {"phase": "validation"},
            app_module.handle_patient_processing,
            app_module.status.HTTP_502_BAD_GATEWAY,
            "patient-processing",
            {"phase": "validation"},
        ),
    ],
)
def test_problem_details_sanitize_document_identifier(
    monkeypatch: pytest.MonkeyPatch,
    exception_cls: type[Exception],
    exception_kwargs: dict[str, Any],
    handler: Callable[..., Any],
    status_code: int,
    type_suffix: str,
    expected_processing_error: dict[str, Any] | None,
) -> None:
    """Exception handlers should expose sanitized problem details."""

    async def _raiser(
        collection: str, document_id: str
    ) -> tuple[UUID, list[TransformationEvent]]:
        raise exception_cls("boom", **exception_kwargs)

    monkeypatch.setattr(app_module, "process_patient", _raiser)

    with pytest.raises(exception_cls):
        asyncio.run(app_module.anonymize_document("patients", "Sensitive-42"))

    surrogate = app_module._document_surrogate_id({"document_id": "Sensitive-42"})
    request = _StubRequest(
        url="http://test/anonymizer/collections/patients/documents/Sensitive-42",
        path_params={"document_id": "Sensitive-42"},
    )

    response = asyncio.run(handler(request, exception_cls("boom", **exception_kwargs)))
    assert response.status_code == status_code

    body = response.content
    assert isinstance(body, dict)
    assert body.get("documentSurrogateId") == surrogate
    assert body.get("type", "").endswith(type_suffix)
    detail = body.get("detail", "")
    if surrogate is not None:
        assert surrogate in detail
    assert "Sensitive-42" not in detail
    if expected_processing_error is None:
        assert "processingError" not in body
    else:
        assert body.get("processingError") == expected_processing_error
        serialized = json.dumps(body.get("processingError"))
        assert "Sensitive-42" not in serialized


class _StubAnonymizer:
    """Minimal anonymizer implementation returning values unchanged."""

    def anonymize(self, value: str, collect_events: bool = False):
        if collect_events:
            return value, []
        return value


@dataclass
class _StubStorage:
    """Storage stub that can simulate persistence failures."""

    error: Exception | None = None
    result_id: UUID | None = None

    def insert_patient(self, record: StoragePatientRow) -> UUID:
        if self.error is not None:
            raise self.error
        self.result_id = uuid4()
        return self.result_id


class _FailingFirestore(FirestoreDataSource):
    """Firestore stub that raises an unexpected runtime error."""

    def get_patient(
        self, collection: str, document_id: str
    ) -> Mapping[str, Any] | None:
        raise RuntimeError("network failure")


class _ValidFirestore(FirestoreDataSource):
    """Firestore stub that returns a minimal valid patient document."""

    def get_patient(
        self, collection: str, document_id: str
    ) -> Mapping[str, Any] | None:
        return {"name": {"first": "Alice", "last": "Example"}}


def _assert_phase(exc: service_module.PatientProcessingError, phase: str) -> None:
    assert exc.phase == phase
    assert dict(exc.details) == {"phase": phase}


def test_process_patient_wraps_fetch_errors_with_phase_details() -> None:
    """Unexpected Firestore failures should surface as fetch phase errors."""

    storage = _StubStorage()

    with pytest.raises(service_module.PatientProcessingError) as excinfo:
        asyncio.run(
            service_module.process_patient(
                "patients",
                "doc-123",
                firestore=_FailingFirestore(),
                anonymizer=_StubAnonymizer(),
                storage=storage,
            )
        )

    _assert_phase(excinfo.value, "fetch")


def test_process_patient_wraps_validation_errors_with_phase_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validation errors should surface with the validation phase metadata."""

    storage = _StubStorage()

    def _raise_validation(cls, payload):  # pragma: no cover - deterministic stub
        raise service_module.ValidationError("invalid payload")

    monkeypatch.setattr(
        service_module.FirestorePatientDocument,
        "model_validate",
        classmethod(_raise_validation),
    )

    with pytest.raises(service_module.PatientProcessingError) as excinfo:
        asyncio.run(
            service_module.process_patient(
                "patients",
                "doc-456",
                firestore=_ValidFirestore(),
                anonymizer=_StubAnonymizer(),
                storage=storage,
            )
        )

    _assert_phase(excinfo.value, "validation")


def test_process_patient_wraps_storage_errors_with_phase_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Storage failures should propagate with storage phase metadata."""

    storage = _StubStorage(error=StorageError("database unavailable"))
    sample_row = StoragePatientRow(
        tenant_id=uuid4(),
        facility_id=uuid4(),
        name_first="Anon",
        name_last="Patient",
        gender="unknown",
        status="inactive",
    )

    def _fake_anonymize(*args, **_kwargs):  # pragma: no cover - deterministic stub
        return args[1]

    monkeypatch.setattr(service_module, "_anonymize_document", _fake_anonymize)
    monkeypatch.setattr(
        service_module, "_convert_to_patient_row", lambda **_: sample_row
    )

    with pytest.raises(service_module.PatientProcessingError) as excinfo:
        asyncio.run(
            service_module.process_patient(
                "patients",
                "doc-789",
                firestore=_ValidFirestore(),
                anonymizer=_StubAnonymizer(),
                storage=storage,
            )
        )

    _assert_phase(excinfo.value, "storage")


def test_process_patient_logs_aggregate_transformation_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persisted patient log entries should only expose aggregate transformation data."""

    storage = _StubStorage()
    sample_row = StoragePatientRow(
        tenant_id=uuid4(),
        facility_id=uuid4(),
        name_first="Anon",
        name_last="Patient",
        gender="unknown",
        status="inactive",
    )

    events = [
        service_module.TransformationEvent(
            entity_type="PERSON",
            action="replace",
            start=0,
            end=5,
            surrogate="Alice Example",
        ),
        service_module.TransformationEvent(
            entity_type="DATE_TIME",
            action="redact",
            start=10,
            end=18,
            surrogate="1990-01-01",
        ),
        service_module.TransformationEvent(
            entity_type="PERSON",
            action="replace",
            start=20,
            end=25,
            surrogate="Bob Example",
        ),
    ]

    def _fake_anonymize(_engine, document, accumulator):
        if accumulator is not None:
            accumulator.extend(events)
        return document

    monkeypatch.setattr(service_module, "_anonymize_document", _fake_anonymize)
    monkeypatch.setattr(
        service_module, "_convert_to_patient_row", lambda **_: sample_row
    )

    class _CapturingLogger:
        def __init__(self) -> None:
            self.records: list[dict[str, Any]] = []

        def bind(
            self, **_kwargs: Any
        ) -> "_CapturingLogger":  # pragma: no cover - passthrough
            return self

        def info(self, message: str, **kwargs: Any) -> None:
            self.records.append({"message": message, "kwargs": kwargs})

    logger = _CapturingLogger()
    monkeypatch.setattr(service_module, "logger", logger)

    patient_id, transformation_events = asyncio.run(
        service_module.process_patient(
            "patients",
            "doc-aggregate",
            firestore=_ValidFirestore(),
            anonymizer=_StubAnonymizer(),
            storage=storage,
        )
    )

    assert isinstance(patient_id, UUID)
    assert len(transformation_events) == len(events)

    persisted_log = next(
        record
        for record in logger.records
        if record["kwargs"].get("event") == "anonymizer.patient.persisted"
    )

    expected_summary = {
        "total_transformations": 3,
        "actions": {"redact": 1, "replace": 2},
        "entities": {
            "DATE_TIME": {"count": 1, "actions": {"redact": 1}},
            "PERSON": {"count": 2, "actions": {"replace": 2}},
        },
    }

    logged_summary = persisted_log["kwargs"].get("transformation_summary")
    assert logged_summary == expected_summary
    assert (
        persisted_log["kwargs"].get("total_transformations")
        == expected_summary["total_transformations"]
    )
    assert (
        persisted_log["kwargs"].get("transformation_actions")
        == expected_summary["actions"]
    )
    assert (
        persisted_log["kwargs"].get("transformation_entities")
        == expected_summary["entities"]
    )
    assert "Alice" not in repr(persisted_log)
