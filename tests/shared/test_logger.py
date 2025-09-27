"""Tests for the shared observability logging helpers."""

from __future__ import annotations

import importlib
import importlib.util
import sys
import types
from contextlib import contextmanager

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class _StructlogStub(types.ModuleType):
    """Minimal stand-in for ``structlog`` used by the logger module tests."""

    def __init__(self) -> None:
        super().__init__("structlog")
        self._context: dict[str, object] = {}

        class _ContextVars:
            def __init__(self, parent: _StructlogStub) -> None:
                self._parent = parent

            def bind_contextvars(self, **values: object) -> None:
                self._parent._context.update(values)

            def unbind_contextvars(self, *keys: str) -> None:
                for key in keys:
                    self._parent._context.pop(key, None)

            def get_contextvars(self) -> dict[str, object]:
                return dict(self._parent._context)

            def clear_contextvars(self) -> None:  # pragma: no cover - convenience helper
                self._parent._context.clear()

            def merge_contextvars(self, logger, method: str, event_dict: dict[str, object]):
                merged = dict(self._parent._context)
                merged.update(event_dict)
                return merged

        self.contextvars = _ContextVars(self)

        class _Processors(types.SimpleNamespace):
            def add_log_level(self, logger, name, event_dict):  # pragma: no cover - passthrough
                return event_dict

            def TimeStamper(self, **kwargs):  # pragma: no cover - passthrough
                return lambda logger, name, event_dict: event_dict

            def StackInfoRenderer(self):  # pragma: no cover - passthrough
                return lambda logger, name, event_dict: event_dict

            def format_exc_info(self, logger, name, event_dict):  # pragma: no cover - passthrough
                return event_dict

            def JSONRenderer(self):  # pragma: no cover - passthrough
                return lambda logger, name, event_dict: event_dict

        self.processors = _Processors()

        class _DummyBoundLogger:
            def bind(self, *_, **__):  # pragma: no cover - passthrough
                return self

            def info(self, *_, **__):  # pragma: no cover - passthrough
                return None

            def exception(self, *_, **__):  # pragma: no cover - passthrough
                return None

        class _StdLib(types.SimpleNamespace):
            def LoggerFactory(self):  # pragma: no cover - passthrough
                return object()

            BoundLogger = _DummyBoundLogger

        self.stdlib = _StdLib()

        def configure(*_, **__):  # pragma: no cover - passthrough
            return None

        def get_logger(name: str | None = None) -> _DummyBoundLogger:  # pragma: no cover
            return _DummyBoundLogger()

        self.configure = configure
        self.get_logger = get_logger


class _LoguruStub(types.ModuleType):
    """Lightweight replacement for :mod:`loguru` required by the logger module."""

    class _Logger:
        def __init__(self) -> None:
            self.extra: dict[str, object] = {}

        def remove(self) -> None:  # pragma: no cover - passthrough
            return None

        def add(self, *_, **__):  # pragma: no cover - passthrough
            return 0

        def configure(self, *, extra: dict[str, object] | None = None, **__):
            if extra:
                self.extra.update(extra)

        def bind(self, *_, **__):  # pragma: no cover - passthrough
            return self

        def level(self, name: str):  # pragma: no cover - passthrough
            return types.SimpleNamespace(name=name)

        def opt(self, *_, **__):  # pragma: no cover - passthrough
            return self

        def log(self, *_, **__):  # pragma: no cover - passthrough
            return None

        def info(self, *_, **__):  # pragma: no cover - passthrough
            return None

        def exception(self, *_, **__):  # pragma: no cover - passthrough
            return None

        @contextmanager
        def contextualize(self, **__):
            yield None

    def __init__(self) -> None:
        super().__init__("loguru")
        self.logger = self._Logger()


@pytest.fixture
def logger_module(monkeypatch: pytest.MonkeyPatch):
    """Import :mod:`shared.observability.logger` with stubbed dependencies."""

    structlog_stub = _StructlogStub()
    loguru_stub = _LoguruStub()

    monkeypatch.setitem(sys.modules, "structlog", structlog_stub)
    monkeypatch.setitem(sys.modules, "loguru", loguru_stub)

    shared_pkg = types.ModuleType("shared")
    shared_pkg.__path__ = []  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "shared", shared_pkg)

    observability_pkg = types.ModuleType("shared.observability")
    observability_pkg.__path__ = []  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "shared.observability", observability_pkg)

    module_path = PROJECT_ROOT / "shared" / "observability" / "logger.py"
    spec = importlib.util.spec_from_file_location(
        "shared.observability.logger", module_path
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["shared.observability.logger"] = module
    spec.loader.exec_module(module)

    yield module, structlog_stub

    structlog_stub.contextvars.clear_contextvars()
    sys.modules.pop("shared.observability.logger", None)


def test_request_context_preserves_service_binding(logger_module) -> None:
    module, structlog_stub = logger_module

    module.configure_logging(service_name="test-service")
    assert structlog_stub.contextvars.get_contextvars()["service"] == "test-service"

    with module.request_context():
        pass

    assert structlog_stub.contextvars.get_contextvars()["service"] == "test-service"


def test_request_context_restores_existing_values(logger_module) -> None:
    module, structlog_stub = logger_module

    module.configure_logging(service_name="outer-service")
    structlog_stub.contextvars.bind_contextvars(request_id="outer", custom="value")

    with module.request_context():
        pass

    context = structlog_stub.contextvars.get_contextvars()
    assert context["service"] == "outer-service"
    assert context["request_id"] == "outer"
    assert context["custom"] == "value"
