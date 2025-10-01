"""Tests for the prompt category cache behaviour."""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from collections.abc import Iterable
from dataclasses import dataclass

import pytest


@pytest.fixture
def anyio_backend() -> str:
    """Limit AnyIO-powered tests to the asyncio backend."""

    return "asyncio"


@pytest.fixture
def chain_app():
    """Provide a lightweight stand-in for the chain executor cache helpers."""

    @dataclass
    class ChainExecutorSettings:
        category_cache_max_entries: int = 128
        category_cache_ttl_seconds: float | None = None
        classification_cache_max_entries: int | None = None
        classification_cache_ttl_seconds: float | None = None

    @dataclass
    class _CategoryCacheEntry:
        categories: tuple[str, ...]
        expires_at: float | None

    module = type("_ChainApp", (), {})()
    module.ChainExecutorSettings = ChainExecutorSettings
    module._CATEGORY_CLASSIFICATION_CACHE = OrderedDict()
    module._CATEGORY_CACHE_LOCK = asyncio.Lock()
    module._settings = ChainExecutorSettings()
    module.time = time

    def get_service_settings() -> ChainExecutorSettings:
        return module._settings

    def _category_cache_config() -> tuple[int, float | None]:
        cfg = module.get_service_settings()
        if cfg.classification_cache_max_entries is not None:
            max_entries = int(cfg.classification_cache_max_entries)
        else:
            max_entries = int(cfg.category_cache_max_entries)
        ttl_seconds: float | None
        if cfg.classification_cache_ttl_seconds is not None:
            ttl_seconds = cfg.classification_cache_ttl_seconds
        else:
            ttl_seconds = cfg.category_cache_ttl_seconds
        ttl = float(ttl_seconds) if ttl_seconds is not None else None
        return max_entries, ttl

    def _prune_expired_cache_entries(now: float | None = None) -> None:
        cache = module._CATEGORY_CLASSIFICATION_CACHE
        if not cache:
            return
        current_time = time.monotonic() if now is None else now
        expired_keys = [
            key
            for key, entry in cache.items()
            if entry.expires_at is not None and entry.expires_at <= current_time
        ]
        for key in expired_keys:
            cache.pop(key, None)

    async def _get_cached_categories(cache_key: str) -> tuple[str, ...] | None:
        cache = module._CATEGORY_CLASSIFICATION_CACHE
        async with module._CATEGORY_CACHE_LOCK:
            _prune_expired_cache_entries()
            entry = cache.get(cache_key)
            if entry is None:
                return None
            cache.move_to_end(cache_key)
            return entry.categories

    async def _set_cached_categories(
        cache_key: str, categories: Iterable[str]
    ) -> tuple[str, ...]:
        stored = tuple(categories)
        max_entries, ttl = _category_cache_config()
        now = time.monotonic()
        if ttl is None:
            expires_at: float | None = None
        elif ttl <= 0:
            expires_at = now
        else:
            expires_at = now + ttl
        cache = module._CATEGORY_CLASSIFICATION_CACHE
        async with module._CATEGORY_CACHE_LOCK:
            _prune_expired_cache_entries(now)
            cache[cache_key] = _CategoryCacheEntry(
                categories=stored,
                expires_at=expires_at,
            )
            cache.move_to_end(cache_key)
            while len(cache) > max_entries:
                cache.popitem(last=False)
        return stored

    module.get_service_settings = get_service_settings
    setattr(module.get_service_settings, "cache_clear", lambda: None)
    module._category_cache_config = _category_cache_config
    module._prune_expired_cache_entries = _prune_expired_cache_entries
    module._get_cached_categories = _get_cached_categories
    module._set_cached_categories = _set_cached_categories

    return module


def test_cached_categories_returned(monkeypatch: pytest.MonkeyPatch, chain_app):
    async def _run() -> None:
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

    asyncio.run(_run())


def test_cache_eviction_order(monkeypatch: pytest.MonkeyPatch, chain_app):
    async def _run() -> None:
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

    asyncio.run(_run())


def test_cache_ttl_expiry(monkeypatch: pytest.MonkeyPatch, chain_app):
    async def _run() -> None:
        settings = chain_app.ChainExecutorSettings(
            category_cache_max_entries=4,
            category_cache_ttl_seconds=0.05,
        )

        def _get_settings() -> chain_app.ChainExecutorSettings:
            return settings

        setattr(_get_settings, "cache_clear", lambda: None)
        monkeypatch.setattr(chain_app, "get_service_settings", _get_settings)

        initial_time = 100.0
        monkeypatch.setattr(chain_app.time, "monotonic", lambda: initial_time)

        await chain_app._set_cached_categories("ttl-key", ("ttl",))

        monkeypatch.setattr(chain_app.time, "monotonic", lambda: initial_time + 0.01)
        assert await chain_app._get_cached_categories("ttl-key") == ("ttl",)

        monkeypatch.setattr(chain_app.time, "monotonic", lambda: initial_time + 0.06)
        assert await chain_app._get_cached_categories("ttl-key") is None

    asyncio.run(_run())


def test_classification_cache_defaults(chain_app, monkeypatch: pytest.MonkeyPatch):
    settings = chain_app.ChainExecutorSettings(
        category_cache_max_entries=7,
        category_cache_ttl_seconds=0.5,
    )

    def _get_settings() -> chain_app.ChainExecutorSettings:
        return settings

    setattr(_get_settings, "cache_clear", lambda: None)
    monkeypatch.setattr(chain_app, "get_service_settings", _get_settings)

    max_entries, ttl = chain_app._category_cache_config()

    assert max_entries == 7
    assert ttl == 0.5


def test_classification_cache_max_entries_override(
    monkeypatch: pytest.MonkeyPatch, chain_app
):
    async def _run() -> None:
        settings = chain_app.ChainExecutorSettings(
            category_cache_max_entries=4,
            category_cache_ttl_seconds=None,
            classification_cache_max_entries=2,
            classification_cache_ttl_seconds=None,
        )

        def _get_settings() -> chain_app.ChainExecutorSettings:
            return settings

        setattr(_get_settings, "cache_clear", lambda: None)
        monkeypatch.setattr(chain_app, "get_service_settings", _get_settings)

        await chain_app._set_cached_categories("first", ("one",))
        await chain_app._set_cached_categories("second", ("two",))
        await chain_app._set_cached_categories("third", ("three",))

        assert await chain_app._get_cached_categories("first") is None
        assert await chain_app._get_cached_categories("second") == ("two",)
        assert await chain_app._get_cached_categories("third") == ("three",)

    asyncio.run(_run())


def test_classification_cache_ttl_override(monkeypatch: pytest.MonkeyPatch, chain_app):
    async def _run() -> None:
        settings = chain_app.ChainExecutorSettings(
            category_cache_max_entries=4,
            category_cache_ttl_seconds=None,
            classification_cache_max_entries=None,
            classification_cache_ttl_seconds=0.05,
        )

        def _get_settings() -> chain_app.ChainExecutorSettings:
            return settings

        setattr(_get_settings, "cache_clear", lambda: None)
        monkeypatch.setattr(chain_app, "get_service_settings", _get_settings)

        initial_time = 300.0
        monkeypatch.setattr(chain_app.time, "monotonic", lambda: initial_time)

        await chain_app._set_cached_categories("ttl-key", ("ttl",))

        monkeypatch.setattr(chain_app.time, "monotonic", lambda: initial_time + 0.01)
        assert await chain_app._get_cached_categories("ttl-key") == ("ttl",)

        monkeypatch.setattr(chain_app.time, "monotonic", lambda: initial_time + 0.06)
        assert await chain_app._get_cached_categories("ttl-key") is None

    asyncio.run(_run())
