from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from services.anonymizer.firestore.client import (
    CredentialedFirestoreDataSource,
    FirestoreConfigurationError,
    FixtureFirestoreDataSource,
    create_firestore_data_source,
)
from services.anonymizer.firestore.client import (
    ENV_CREDENTIALS,
    ENV_DATA_SOURCE,
    ENV_FIXTURE_DIRECTORY,
    MODE_CREDENTIALS,
    MODE_FIXTURES,
)


def test_fixture_data_source_returns_patient_from_default_fixtures() -> None:
    data_source = FixtureFirestoreDataSource()

    patient = data_source.get_patient("patients", "xpF51IBED5TOKMPJamWo")

    assert patient is not None
    assert patient["name"]["first"] == "Nick"


def test_fixture_data_source_returns_none_for_missing_patient() -> None:
    data_source = FixtureFirestoreDataSource()

    assert data_source.get_patient("patients", "unknown") is None


@pytest.mark.parametrize("collection", ["clinicians", "", "Facilities"])
def test_fixture_data_source_returns_none_for_mismatched_collection(collection: str) -> None:
    data_source = FixtureFirestoreDataSource()

    assert data_source.get_patient(collection, "xpF51IBED5TOKMPJamWo") is None


def test_create_firestore_data_source_defaults_to_fixture_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_DATA_SOURCE, raising=False)
    monkeypatch.delenv(ENV_FIXTURE_DIRECTORY, raising=False)

    data_source = create_firestore_data_source()

    assert isinstance(data_source, FixtureFirestoreDataSource)


def test_create_firestore_data_source_uses_custom_fixture_directory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fixture = tmp_path / "patients"
    fixture.mkdir()
    payload = fixture / "example.json"
    payload.write_text("{}", encoding="utf-8")

    monkeypatch.setenv(ENV_FIXTURE_DIRECTORY, str(fixture))
    monkeypatch.delenv(ENV_DATA_SOURCE, raising=False)

    data_source = create_firestore_data_source()

    assert isinstance(data_source, FixtureFirestoreDataSource)


def test_create_firestore_data_source_validates_fixture_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_FIXTURE_DIRECTORY, "/does/not/exist")

    with pytest.raises(FirestoreConfigurationError):
        create_firestore_data_source()


def test_create_firestore_data_source_with_credentials_requires_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_DATA_SOURCE, MODE_CREDENTIALS)
    monkeypatch.delenv(ENV_CREDENTIALS, raising=False)

    with pytest.raises(FirestoreConfigurationError):
        create_firestore_data_source()


def test_create_firestore_data_source_with_credentials_returns_placeholder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text("{}", encoding="utf-8")

    monkeypatch.setenv(ENV_DATA_SOURCE, MODE_CREDENTIALS)
    monkeypatch.setenv(ENV_CREDENTIALS, str(credentials_path))

    data_source = create_firestore_data_source()

    assert isinstance(data_source, CredentialedFirestoreDataSource)


def test_create_firestore_data_source_with_unknown_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_DATA_SOURCE, "unknown")

    with pytest.raises(FirestoreConfigurationError):
        create_firestore_data_source()
