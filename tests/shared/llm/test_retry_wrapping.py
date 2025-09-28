"""Tests for retry helpers in :mod:`shared.llm.adapters._base`."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def stub_dependencies(monkeypatch):
    """Provide lightweight stubs for optional runtime dependencies."""

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3]))

    project_root = Path(__file__).resolve().parents[3]

    settings_module = types.ModuleType("shared.config.settings")

    class Settings:
        def __init__(self) -> None:
            self.default_model = types.SimpleNamespace(temperature=None)

    def get_settings() -> Settings:
        return Settings()

    settings_module.Settings = Settings
    settings_module.get_settings = get_settings
    monkeypatch.setitem(sys.modules, "shared.config.settings", settings_module)

    shared_pkg = types.ModuleType("shared")
    shared_pkg.__path__ = [str(project_root / "shared")]
    monkeypatch.setitem(sys.modules, "shared", shared_pkg)

    llm_pkg = types.ModuleType("shared.llm")
    llm_pkg.__path__ = [str(project_root / "shared" / "llm")]
    monkeypatch.setitem(sys.modules, "shared.llm", llm_pkg)

    adapters_pkg = types.ModuleType("shared.llm.adapters")
    adapters_pkg.__path__ = [str(project_root / "shared" / "llm" / "adapters")]
    monkeypatch.setitem(sys.modules, "shared.llm.adapters", adapters_pkg)

    logger_module = types.ModuleType("shared.observability.logger")

    class _Logger:
        def warning(self, *args, **kwargs):
            pass

        def exception(self, *args, **kwargs):
            pass

    def get_logger(_name: str) -> _Logger:
        return _Logger()

    logger_module.get_logger = get_logger
    monkeypatch.setitem(sys.modules, "shared.observability.logger", logger_module)

    langchain_core = types.ModuleType("langchain_core")
    language_models = types.ModuleType("langchain_core.language_models")

    class BaseLanguageModel:  # pragma: no cover - minimal test stub
        def invoke(self, *_args, **_kwargs):
            raise NotImplementedError

        async def ainvoke(self, *_args, **_kwargs):
            raise NotImplementedError

    language_models.BaseLanguageModel = BaseLanguageModel
    langchain_core.language_models = language_models
    monkeypatch.setitem(sys.modules, "langchain_core", langchain_core)
    monkeypatch.setitem(sys.modules, "langchain_core.language_models", language_models)

    tenacity = types.ModuleType("tenacity")

    class RetryCallState:
        def __init__(self, attempt_number: int, outcome=None, next_action=None) -> None:
            self.attempt_number = attempt_number
            self.outcome = outcome
            self.next_action = next_action

    class _Outcome:
        def __init__(self, exception: BaseException) -> None:
            self._exception = exception
            self.failed = True

        def exception(self) -> BaseException:
            return self._exception

    class _RetryCondition:
        def __init__(self, predicate):
            self._predicate = predicate

        def __call__(self, exc: BaseException) -> bool:
            return self._predicate(exc)

        def __and__(self, other):
            return _RetryCondition(lambda exc: self(exc) and other(exc))

        def __invert__(self):
            return _RetryCondition(lambda exc: not self(exc))

    def retry_if_exception_type(exc_type):
        if isinstance(exc_type, tuple):
            exceptions = exc_type
        else:
            exceptions = (exc_type,)
        return _RetryCondition(lambda exc: isinstance(exc, exceptions))

    class _StopPolicy:
        def __init__(self, max_attempts: int) -> None:
            self.max_attempts = max_attempts

    def stop_after_attempt(max_attempts: int) -> _StopPolicy:
        return _StopPolicy(max_attempts)

    class _WaitPolicy:
        def __init__(
            self, **_kwargs
        ) -> None:  # pragma: no cover - behaviour not exercised
            pass

    def wait_exponential(
        **kwargs,
    ) -> _WaitPolicy:  # pragma: no cover - behaviour not exercised
        return _WaitPolicy(**kwargs)

    class _BaseAttempt:
        def __init__(self, parent) -> None:
            self._parent = parent

        def _handle_exit(self, exc_type, exc):
            if exc is None:
                self._parent._complete = True
                return False
            should_retry = self._parent.retry(exc)
            if (not should_retry) or (
                self._parent.attempt_number >= self._parent.max_attempts
            ):
                self._parent._complete = True
                return False
            if self._parent.before_sleep:
                state = RetryCallState(
                    attempt_number=self._parent.attempt_number,
                    outcome=_Outcome(exc),
                    next_action=types.SimpleNamespace(sleep=None),
                )
                self._parent.before_sleep(state)
            return True

    class _SyncAttempt(_BaseAttempt):
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, _tb):
            return self._handle_exit(exc_type, exc)

    class _AsyncAttempt(_BaseAttempt):
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, _tb):
            return self._handle_exit(exc_type, exc)

        async def __aenter__(self):  # pragma: no cover - compatibility shim
            return self

        async def __aexit__(
            self, exc_type, exc, _tb
        ):  # pragma: no cover - compatibility shim
            return self._handle_exit(exc_type, exc)

    class Retrying:
        def __init__(self, *, stop, retry, before_sleep=None, **_kwargs) -> None:
            self.max_attempts = getattr(stop, "max_attempts", stop)
            self.retry = retry
            self.before_sleep = before_sleep
            self.attempt_number = 0
            self._complete = False

        def __iter__(self):
            return self

        def __next__(self):
            if self._complete or self.attempt_number >= self.max_attempts:
                raise StopIteration
            self.attempt_number += 1
            return _SyncAttempt(self)

    class AsyncRetrying:
        def __init__(self, *, stop, retry, before_sleep=None, **_kwargs) -> None:
            self.max_attempts = getattr(stop, "max_attempts", stop)
            self.retry = retry
            self.before_sleep = before_sleep
            self.attempt_number = 0
            self._complete = False

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._complete or self.attempt_number >= self.max_attempts:
                raise StopAsyncIteration
            self.attempt_number += 1
            return _AsyncAttempt(self)

    tenacity.AsyncRetrying = AsyncRetrying
    tenacity.RetryCallState = RetryCallState
    tenacity.Retrying = Retrying
    tenacity.retry_if_exception_type = retry_if_exception_type
    tenacity.stop_after_attempt = stop_after_attempt
    tenacity.wait_exponential = wait_exponential

    monkeypatch.setitem(sys.modules, "tenacity", tenacity)

    yield


def test_cancelled_error_is_not_retried():
    """Ensure ``asyncio.CancelledError`` is not retried by the wrappers."""

    module_path = (
        Path(__file__).resolve().parents[3] / "shared" / "llm" / "adapters" / "_base.py"
    )
    spec = importlib.util.spec_from_file_location(
        "shared.llm.adapters._base", module_path
    )
    assert spec and spec.loader
    base_module = importlib.util.module_from_spec(spec)
    sys.modules["shared.llm.adapters._base"] = base_module
    spec.loader.exec_module(base_module)

    class DummyModel:
        def __init__(self) -> None:
            self.attempts = 0

        async def ainvoke(self, *args, **kwargs):
            self.attempts += 1
            raise asyncio.CancelledError()

    model = DummyModel()
    wrapped = base_module.attach_retry(model, label="dummy", max_attempts=3)

    async def invoke_once() -> None:
        await wrapped.ainvoke()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(invoke_once())

    assert model.attempts == 1


def test_ensure_langchain_compat_replaces_stub_invoke():
    """Legacy models falling back to ``__call__`` gain ``invoke``."""

    module_path = (
        Path(__file__).resolve().parents[3] / "shared" / "llm" / "adapters" / "_base.py"
    )
    spec = importlib.util.spec_from_file_location(
        "shared.llm.adapters._base", module_path
    )
    assert spec and spec.loader
    base_module = importlib.util.module_from_spec(spec)
    sys.modules["shared.llm.adapters._base"] = base_module
    spec.loader.exec_module(base_module)

    class LegacyModel(base_module.BaseLanguageModel):
        def __call__(self, value: str) -> str:
            return f"legacy {value}"

    LegacyModel.__abstractmethods__ = frozenset()

    model = LegacyModel()
    patched = base_module.ensure_langchain_compat(model)

    assert patched.invoke("value") == "legacy value"


def test_ensure_langchain_compat_replaces_stub_ainvoke():
    """Legacy async models fall back to ``apredict`` for ``ainvoke``."""

    module_path = (
        Path(__file__).resolve().parents[3] / "shared" / "llm" / "adapters" / "_base.py"
    )
    spec = importlib.util.spec_from_file_location(
        "shared.llm.adapters._base", module_path
    )
    assert spec and spec.loader
    base_module = importlib.util.module_from_spec(spec)
    sys.modules["shared.llm.adapters._base"] = base_module
    spec.loader.exec_module(base_module)

    class LegacyAsyncModel(base_module.BaseLanguageModel):
        async def apredict(self, value: str) -> str:
            return f"async {value}"

    LegacyAsyncModel.__abstractmethods__ = frozenset()

    model = LegacyAsyncModel()
    patched = base_module.ensure_langchain_compat(model)

    assert asyncio.run(patched.ainvoke("value")) == "async value"
