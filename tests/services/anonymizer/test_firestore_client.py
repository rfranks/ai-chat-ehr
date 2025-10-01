from __future__ import annotations

# ruff: noqa: E402

from pathlib import Path
import sys
import types
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest

if "dotenv" not in sys.modules:
    dotenv_stub = types.ModuleType("dotenv")
    dotenv_stub.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = dotenv_stub

if "services.anonymizer" not in sys.modules:
    anonymizer_stub = types.ModuleType("services.anonymizer")
    anonymizer_stub.__path__ = [str(PROJECT_ROOT / "services" / "anonymizer")]
    sys.modules["services.anonymizer"] = anonymizer_stub

if "presidio_analyzer" not in sys.modules:
    presidio_stub = types.ModuleType("presidio_analyzer")

    class _AnalyzerEngine:
        def __init__(self) -> None:
            self.registry = types.SimpleNamespace(
                add_recognizer=lambda *args, **kwargs: None
            )

    class _Pattern:
        def __init__(
            self, *args: Any, **kwargs: Any
        ) -> None:  # pragma: no cover - simple stub
            self.args = args
            self.kwargs = kwargs

    class _PatternRecognizer:
        def __init__(
            self, *args: Any, **kwargs: Any
        ) -> None:  # pragma: no cover - simple stub
            self.args = args
            self.kwargs = kwargs

    class _RecognizerResult:
        pass

    presidio_stub.AnalyzerEngine = _AnalyzerEngine
    presidio_stub.Pattern = _Pattern
    presidio_stub.PatternRecognizer = _PatternRecognizer
    presidio_stub.RecognizerResult = _RecognizerResult

    sys.modules["presidio_analyzer"] = presidio_stub

from services.anonymizer.firestore.client import (
    CredentialedFirestoreDataSource,
    FirestoreConfigurationError,
    FirestoreDataSourceError,
    FixtureFirestoreDataSource,
    create_firestore_data_source,
)
from services.anonymizer.firestore.client import (
    ENV_CREDENTIALS,
    ENV_DATA_SOURCE,
    ENV_FIXTURE_DIRECTORY,
    ENV_PROJECT_ID,
    MODE_CREDENTIALS,
)


class _StubDocumentSnapshot:
    def __init__(self, *, exists: bool, payload: Mapping[str, Any] | None) -> None:
        self.exists = exists
        self._payload = payload

    def to_dict(self) -> Mapping[str, Any] | None:
        return self._payload


class _StubDocumentReference:
    def __init__(
        self, *, snapshot: _StubDocumentSnapshot | None, error: Exception | None = None
    ) -> None:
        self._snapshot = snapshot
        self._error = error

    def get(self) -> _StubDocumentSnapshot:
        if self._error:
            raise self._error
        assert self._snapshot is not None
        return self._snapshot


class _StubCollectionReference:
    def __init__(self) -> None:
        self.requests: list[str] = []
        self._document: _StubDocumentReference | None = None

    def set_document(self, document: _StubDocumentReference) -> None:
        self._document = document

    def document(self, document_id: str) -> _StubDocumentReference:
        self.requests.append(document_id)
        assert self._document is not None
        return self._document


class _StubFirestoreClient:
    def __init__(
        self,
        *,
        snapshot: _StubDocumentSnapshot | None = None,
        error: Exception | None = None,
    ) -> None:
        self.collection_calls: list[str] = []
        self._collection = _StubCollectionReference()
        self._collection.set_document(
            _StubDocumentReference(snapshot=snapshot, error=error)
        )

    def collection(self, name: str) -> _StubCollectionReference:
        self.collection_calls.append(name)
        return self._collection


def test_fixture_data_source_returns_patient_from_default_fixtures() -> None:
    data_source = FixtureFirestoreDataSource()

    patient = data_source.get_patient("patients", "xpF51IBED5TOKMPJamWo")

    assert patient is not None
    assert patient["name"]["first"] == "Nick"


def test_fixture_data_source_returns_none_for_missing_patient() -> None:
    data_source = FixtureFirestoreDataSource()

    assert data_source.get_patient("patients", "unknown") is None


@pytest.mark.parametrize("collection", ["clinicians", "", "Facilities"])
def test_fixture_data_source_returns_none_for_mismatched_collection(
    collection: str,
) -> None:
    data_source = FixtureFirestoreDataSource()

    assert data_source.get_patient(collection, "xpF51IBED5TOKMPJamWo") is None


def test_create_firestore_data_source_defaults_to_fixture_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(ENV_DATA_SOURCE, raising=False)
    monkeypatch.delenv(ENV_FIXTURE_DIRECTORY, raising=False)

    data_source = create_firestore_data_source()

    assert isinstance(data_source, FixtureFirestoreDataSource)


def test_create_firestore_data_source_trims_env_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ENV_DATA_SOURCE, "  fixtures  ")

    data_source = create_firestore_data_source()

    try:
        assert isinstance(data_source, FixtureFirestoreDataSource)
    finally:
        monkeypatch.delenv(ENV_DATA_SOURCE, raising=False)


def test_create_firestore_data_source_uses_custom_fixture_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fixture = tmp_path / "patients"
    fixture.mkdir()
    payload = fixture / "example.json"
    payload.write_text("{}", encoding="utf-8")

    monkeypatch.setenv(ENV_FIXTURE_DIRECTORY, str(fixture))
    monkeypatch.delenv(ENV_DATA_SOURCE, raising=False)

    data_source = create_firestore_data_source()

    assert isinstance(data_source, FixtureFirestoreDataSource)


def test_create_firestore_data_source_validates_fixture_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ENV_FIXTURE_DIRECTORY, "/does/not/exist")

    with pytest.raises(FirestoreConfigurationError):
        create_firestore_data_source()


def test_create_firestore_data_source_with_credentials_requires_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ENV_DATA_SOURCE, MODE_CREDENTIALS)
    monkeypatch.delenv(ENV_CREDENTIALS, raising=False)

    with pytest.raises(FirestoreConfigurationError):
        create_firestore_data_source()


def test_create_firestore_data_source_with_credentials_returns_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        CredentialedFirestoreDataSource,
        "_create_client",
        lambda self: object(),
    )

    monkeypatch.setenv(ENV_DATA_SOURCE, MODE_CREDENTIALS)
    monkeypatch.setenv(ENV_CREDENTIALS, str(credentials_path))
    monkeypatch.setenv(ENV_PROJECT_ID, "example-project")

    data_source = create_firestore_data_source()

    assert isinstance(data_source, CredentialedFirestoreDataSource)
    assert data_source.project_id == "example-project"


def test_create_firestore_data_source_with_unknown_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ENV_DATA_SOURCE, "unknown")

    with pytest.raises(FirestoreConfigurationError):
        create_firestore_data_source()


def test_credentialed_firestore_data_source_returns_document(tmp_path: Path) -> None:
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text("{}", encoding="utf-8")

    snapshot = _StubDocumentSnapshot(exists=True, payload={"name": "Ada"})
    client = _StubFirestoreClient(snapshot=snapshot)

    data_source = CredentialedFirestoreDataSource(
        credentials_path=credentials_path,
        project_id="proj-123",
        client=client,
    )

    patient = data_source.get_patient("patients", "secret-id")

    assert patient == {"name": "Ada"}
    assert client.collection_calls == ["patients"]


def test_credentialed_firestore_data_source_returns_none_for_missing_document(
    tmp_path: Path,
) -> None:
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text("{}", encoding="utf-8")

    snapshot = _StubDocumentSnapshot(exists=False, payload=None)
    client = _StubFirestoreClient(snapshot=snapshot)

    data_source = CredentialedFirestoreDataSource(
        credentials_path=credentials_path,
        client=client,
    )

    assert data_source.get_patient("patients", "secret-id") is None


def test_credentialed_firestore_data_source_wraps_errors(tmp_path: Path) -> None:
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text("{}", encoding="utf-8")

    error = RuntimeError("dangerous secret-id exposed")
    client = _StubFirestoreClient(snapshot=None, error=error)

    data_source = CredentialedFirestoreDataSource(
        credentials_path=credentials_path,
        project_id="proj-123",
        client=client,
    )

    with pytest.raises(FirestoreDataSourceError) as exc_info:
        data_source.get_patient("patients", "secret-id")

    message = str(exc_info.value)
    assert "secret-id" not in message
    assert "<redacted>" in message
    assert "patients" in message
    assert exc_info.value.context == {
        "collection": "patients",
        "document_id": "<redacted>",
        "project_id": "proj-123",
        "error_type": "RuntimeError",
    }
