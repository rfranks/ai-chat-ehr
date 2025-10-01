"""Tests for anonymizer service configuration helpers."""

# ruff: noqa: E402

from __future__ import annotations

from pathlib import Path
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if "dotenv" not in sys.modules:
    dotenv_stub = types.ModuleType("dotenv")

    def load_dotenv(*_args, **_kwargs):  # pragma: no cover - stub helper
        return None

    dotenv_stub.load_dotenv = load_dotenv
    sys.modules["dotenv"] = dotenv_stub

if "presidio_analyzer" not in sys.modules:
    presidio_stub = types.ModuleType("presidio_analyzer")

    class AnalyzerEngine:  # pragma: no cover - stub implementation
        def __init__(self, *args, **kwargs) -> None:
            pass

        def analyze(self, *args, **kwargs):
            return []

        @property
        def registry(self):  # pragma: no cover - stub registry
            class _Registry:
                def add_recognizer(self, *args, **kwargs):
                    return None

            return _Registry()

    class RecognizerResult:  # pragma: no cover - stub
        def __init__(self, *args, **kwargs) -> None:
            pass

    class Pattern:  # pragma: no cover - stub
        def __init__(self, *args, **kwargs) -> None:
            pass

    class PatternRecognizer:  # pragma: no cover - stub
        def __init__(self, *args, **kwargs) -> None:
            pass

    presidio_stub.AnalyzerEngine = AnalyzerEngine
    presidio_stub.Pattern = Pattern
    presidio_stub.PatternRecognizer = PatternRecognizer
    presidio_stub.RecognizerResult = RecognizerResult
    sys.modules["presidio_analyzer"] = presidio_stub

if "pydantic" not in sys.modules:
    pydantic_stub = types.ModuleType("pydantic")

    class BaseModel:  # pragma: no cover - stub implementation
        def __init__(self, **data) -> None:
            for key, value in data.items():
                setattr(self, key, value)

        def model_dump(self, *_, **__) -> dict[str, object]:
            return dict(self.__dict__)

    def Field(default=..., **_kwargs):  # pragma: no cover - stub helper
        return default

    def ConfigDict(**kwargs):  # pragma: no cover - stub helper
        return dict(kwargs)

    class ValidationError(Exception):  # pragma: no cover - stub helper
        pass

    pydantic_stub.BaseModel = BaseModel
    pydantic_stub.Field = Field
    pydantic_stub.ConfigDict = ConfigDict
    pydantic_stub.ValidationError = ValidationError
    sys.modules["pydantic"] = pydantic_stub

if "structlog" not in sys.modules:
    structlog_stub = types.ModuleType("structlog")

    def get_logger(*_args, **_kwargs):  # pragma: no cover - stub helper
        class _Logger:
            def bind(self, *args, **kwargs):  # pragma: no cover - stub helper
                return self

            def info(self, *args, **kwargs):  # pragma: no cover - stub helper
                return None

            def error(self, *args, **kwargs):  # pragma: no cover - stub helper
                return None

        return _Logger()

    structlog_stub.get_logger = get_logger
    sys.modules["structlog"] = structlog_stub

if "loguru" not in sys.modules:
    loguru_stub = types.ModuleType("loguru")

    class _Logger:  # pragma: no cover - stub helper
        def bind(self, *args, **kwargs):
            return self

        def opt(self, *args, **kwargs):
            return self

        def info(self, *args, **kwargs):
            return None

        def warning(self, *args, **kwargs):
            return None

        def error(self, *args, **kwargs):
            return None

        def exception(self, *args, **kwargs):
            return None

    loguru_stub.logger = _Logger()
    sys.modules["loguru"] = loguru_stub

if "starlette" not in sys.modules:
    starlette_stub = types.ModuleType("starlette")
    middleware_stub = types.ModuleType("starlette.middleware")
    base_stub = types.ModuleType("starlette.middleware.base")
    requests_stub = types.ModuleType("starlette.requests")
    responses_stub = types.ModuleType("starlette.responses")
    types_stub = types.ModuleType("starlette.types")

    class BaseHTTPMiddleware:  # pragma: no cover - stub helper
        def __init__(self, *args, **kwargs) -> None:
            pass

    class Request:  # pragma: no cover - stub helper
        pass

    class Response:  # pragma: no cover - stub helper
        pass

    class ASGIApp:  # pragma: no cover - stub helper
        pass

    base_stub.BaseHTTPMiddleware = BaseHTTPMiddleware
    middleware_stub.base = base_stub
    requests_stub.Request = Request
    responses_stub.Response = Response
    types_stub.ASGIApp = ASGIApp
    starlette_stub.middleware = middleware_stub
    starlette_stub.requests = requests_stub
    starlette_stub.responses = responses_stub
    starlette_stub.types = types_stub
    sys.modules["starlette"] = starlette_stub
    sys.modules["starlette.middleware"] = middleware_stub
    sys.modules["starlette.middleware.base"] = base_stub
    sys.modules["starlette.requests"] = requests_stub
    sys.modules["starlette.responses"] = responses_stub
    sys.modules["starlette.types"] = types_stub

from services.anonymizer import service
from services.anonymizer.presidio_engine import PresidioEngineConfig


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(service.ENV_ANONYMIZER_HASH_SECRET, raising=False)
    monkeypatch.delenv(service.ENV_ANONYMIZER_HASH_PREFIX, raising=False)
    monkeypatch.delenv(service.ENV_ANONYMIZER_HASH_LENGTH, raising=False)


def test_presidio_config_defaults_when_env_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_env(monkeypatch)

    config = service._create_presidio_config_from_env()

    default = PresidioEngineConfig()
    assert config.hash_secret == default.hash_secret
    assert config.hash_prefix == default.hash_prefix
    assert config.hash_length == default.hash_length


def test_presidio_config_overrides_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv(service.ENV_ANONYMIZER_HASH_SECRET, "override-secret")
    monkeypatch.setenv(service.ENV_ANONYMIZER_HASH_PREFIX, "override-prefix")
    monkeypatch.setenv(service.ENV_ANONYMIZER_HASH_LENGTH, "24")

    config = service._create_presidio_config_from_env()

    assert config.hash_secret == "override-secret"
    assert config.hash_prefix == "override-prefix"
    assert config.hash_length == 24


def test_configure_service_passes_environment_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv(service.ENV_ANONYMIZER_HASH_SECRET, "configured-secret")

    class StubEngine:
        def __init__(self, *, analyzer=None, config=None, synthesizer=None):
            self.analyzer = analyzer
            self.config = config
            self.synthesizer = synthesizer

    stub_engine = StubEngine()

    def build_engine(*, analyzer=None, config=None, synthesizer=None):
        stub_engine.analyzer = analyzer
        stub_engine.config = config
        stub_engine.synthesizer = synthesizer
        return stub_engine

    monkeypatch.setattr(service, "PresidioAnonymizerEngine", build_engine)
    monkeypatch.setattr(service, "create_firestore_data_source", lambda: object())
    monkeypatch.setattr(service, "_create_storage_from_env", lambda: object())

    service._dependencies = None
    service.configure_service()

    assert isinstance(service._dependencies, service._ServiceDependencies)
    assert isinstance(stub_engine.config, PresidioEngineConfig)
    assert stub_engine.config.hash_secret == "configured-secret"

    service._dependencies = None
