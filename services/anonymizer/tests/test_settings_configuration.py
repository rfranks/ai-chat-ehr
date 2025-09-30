"""Tests ensuring environment driven configuration behaves as expected."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("pydantic")

from services.anonymizer.app.config.settings import Settings, get_settings


def test_settings_resolve_values_from_environment(monkeypatch):
    monkeypatch.setenv("ANONYMIZER_APP__PORT", "9000")
    monkeypatch.setenv("ANONYMIZER_PIPELINE__INCLUDE_DEFAULTED", "true")
    monkeypatch.setenv(
        "ANONYMIZER_PIPELINE__RETURNING",
        json.dumps({"patients": ["patient_id", "status"]}),
    )
    monkeypatch.setenv("ANONYMIZER_FIRESTORE__PROJECT_ID", "test-project")

    settings = Settings()

    assert settings.app.port == 9000
    assert settings.pipeline.include_defaulted is True
    assert settings.pipeline.returning == {"patients": ["patient_id", "status"]}
    assert settings.firestore.project_id == "test-project"


def test_get_settings_returns_cached_instance(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ANONYMIZER_APP__PORT", "9100")

    first = get_settings()
    assert first.app.port == 9100

    # Changing the environment after the initial call should not affect the cached instance.
    monkeypatch.setenv("ANONYMIZER_APP__PORT", "9200")
    second = get_settings()

    assert second is first
    assert second.app.port == 9100

    # Clearing the cache allows refreshed configuration to be loaded.
    get_settings.cache_clear()
    monkeypatch.delenv("ANONYMIZER_APP__PORT", raising=False)
    refreshed = get_settings()

    assert refreshed.app.port == 8004

    get_settings.cache_clear()
