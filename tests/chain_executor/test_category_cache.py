"""Tests for the prompt category cache behaviour."""

from __future__ import annotations

import asyncio
import importlib
import sys
import types
from collections import OrderedDict
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def anyio_backend() -> str:
    """Limit AnyIO-powered tests to the asyncio backend."""

    return "asyncio"


@pytest.fixture
def chain_app(monkeypatch: pytest.MonkeyPatch):
    """Return a freshly imported chain executor module with isolated cache state."""

    logger_module_name = "shared.observability.logger"
    stub = types.ModuleType(logger_module_name)

    class _DummyLogger:
        def bind(self, *args: object, **kwargs: object) -> "_DummyLogger":
            return self

        def info(self, *args: object, **kwargs: object) -> None:
            return None

        def warning(self, *args: object, **kwargs: object) -> None:
            return None

        def exception(self, *args: object, **kwargs: object) -> None:
            return None

        def contextualize(self, *args: object, **kwargs: object):
            @contextmanager
            def _ctx():
                yield None

            return _ctx()

    def configure_logging(*args: Any, **kwargs: Any) -> None:  # pragma: no cover - stub
        return None

    def get_logger(
        *args: Any, **kwargs: Any
    ) -> _DummyLogger:  # pragma: no cover - stub
        return _DummyLogger()

    def generate_request_id() -> str:  # pragma: no cover - stub
        return "stub-request-id"

    def get_request_id() -> str | None:  # pragma: no cover - stub
        return "stub-request-id"

    @contextmanager
    def request_context(*args: Any, **kwargs: Any):  # pragma: no cover - stub
        yield None

    stub.configure_logging = configure_logging
    stub.get_logger = get_logger
    stub.generate_request_id = generate_request_id
    stub.get_request_id = get_request_id
    stub.request_context = request_context

    monkeypatch.setitem(sys.modules, logger_module_name, stub)
    module_name = "services.chain_executor.app"
    sys.modules.pop(module_name, None)
    chain_app = importlib.import_module(module_name)
    if hasattr(chain_app.get_service_settings, "cache_clear"):
        chain_app.get_service_settings.cache_clear()

    monkeypatch.setattr(chain_app, "_CATEGORY_CLASSIFICATION_CACHE", OrderedDict())
    monkeypatch.setattr(chain_app, "_CATEGORY_CACHE_LOCK", asyncio.Lock())

    return chain_app


@pytest.mark.anyio("asyncio")
async def test_cached_categories_returned(monkeypatch: pytest.MonkeyPatch, chain_app):
    settings = chain_app.ChainExecutorSettings(
        category_cache_max_entries=4,
        category_cache_ttl_seconds=None,
    )

    def _get_settings() -> chain_app.ChainExecutorSettings:
        return settings

    setattr(_get_settings, "cache_clear", lambda: None)
    monkeypatch.setattr(chain_app, "get_service_settings", _get_settings)

    await chain_app._set_cached_categories("cache-key", ("alpha", "beta"))
    result = await chain_app._get_cached_categories("cache-key")

    assert result == ("alpha", "beta")


@pytest.mark.anyio("asyncio")
async def test_cache_eviction_order(monkeypatch: pytest.MonkeyPatch, chain_app):
    settings = chain_app.ChainExecutorSettings(
        category_cache_max_entries=2,
        category_cache_ttl_seconds=None,
    )

    def _get_settings() -> chain_app.ChainExecutorSettings:
        return settings

    setattr(_get_settings, "cache_clear", lambda: None)
    monkeypatch.setattr(chain_app, "get_service_settings", _get_settings)

    await chain_app._set_cached_categories("first", ("one",))
    await chain_app._set_cached_categories("second", ("two",))

    assert await chain_app._get_cached_categories("first") == ("one",)

    await chain_app._set_cached_categories("third", ("three",))

    assert await chain_app._get_cached_categories("first") == ("one",)
    assert await chain_app._get_cached_categories("second") is None


@pytest.mark.anyio("asyncio")
async def test_cache_ttl_expiry(monkeypatch: pytest.MonkeyPatch, chain_app):
    settings = chain_app.ChainExecutorSettings(
        category_cache_max_entries=4,
        category_cache_ttl_seconds=0.05,
    )

    def _get_settings() -> chain_app.ChainExecutorSettings:
        return settings

    setattr(_get_settings, "cache_clear", lambda: None)
    monkeypatch.setattr(chain_app, "get_service_settings", _get_settings)

    await chain_app._set_cached_categories("ttl-key", ("ttl",))
    assert await chain_app._get_cached_categories("ttl-key") == ("ttl",)

    await asyncio.sleep(0.06)

    assert await chain_app._get_cached_categories("ttl-key") is None
