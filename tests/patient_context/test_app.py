from __future__ import annotations

import sys
import types
from contextlib import contextmanager
from pathlib import Path
from typing import AsyncIterator, Generator

import pytest
from httpx import ASGITransport, AsyncClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def _stub_logger_module(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    """Provide a lightweight stand-in for the shared logger dependency."""

    module_name = "shared.observability.logger"
    stub = types.ModuleType(module_name)

    class _DummyLogger:
        def bind(self, *args: object, **kwargs: object) -> "_DummyLogger":
            return self  # pragma: no cover - stub

        def info(self, *args: object, **kwargs: object) -> None:
            return None  # pragma: no cover - stub

        def warning(self, *args: object, **kwargs: object) -> None:
            return None  # pragma: no cover - stub

        def contextualize(self, *args: object, **kwargs: object):
            @contextmanager
            def _ctx():
                yield None

            return _ctx()  # pragma: no cover - stub

    def get_logger(name: str | None = None) -> _DummyLogger:
        return _DummyLogger()  # pragma: no cover - stub

    stub.get_logger = get_logger  # type: ignore[attr-defined]
    stub.configure_logging = lambda *args, **kwargs: None  # type: ignore[attr-defined]
    stub.generate_request_id = lambda: "test-request-id"  # type: ignore[attr-defined]
    stub.get_request_id = lambda: "test-request-id"  # type: ignore[attr-defined]

    @contextmanager
    def request_context(*args: object, **kwargs: object):  # pragma: no cover - stub
        yield "test-request-id"

    stub.request_context = request_context  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, module_name, stub)

    yield

    sys.modules.pop(module_name, None)


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    from services.patient_context.app import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",  # FastAPI ignores the host for ASGI transports
    ) as client:
        yield client


@pytest.fixture
def anyio_backend() -> str:
    """Limit ``pytest-anyio`` to the asyncio backend for these tests."""

    return "asyncio"


@pytest.mark.anyio("asyncio")
async def test_read_patient_context_without_filters(client: AsyncClient) -> None:
    response = await client.get("/patients/123456/context")
    assert response.status_code == 200

    payload = response.json()
    assert payload["demographics"]["patientId"] == "123456"
    assert payload["medications"], (
        "Expected medications to be present when no filters are applied"
    )
    assert payload["labResults"], (
        "Expected lab results to be present when no filters are applied"
    )


@pytest.mark.anyio("asyncio")
async def test_read_patient_record(client: AsyncClient) -> None:
    response = await client.get("/patients/123456")
    assert response.status_code == 200

    payload = response.json()
    assert payload["demographics"]["patientId"] == "123456"
    assert payload["medications"], "Expected medications to be present in patient record"
    assert payload["encounters"], "Expected encounters to be present in patient record"


@pytest.mark.anyio("asyncio")
async def test_read_patient_record_unknown_patient(client: AsyncClient) -> None:
    response = await client.get("/patients/999999")
    assert response.status_code == 404

    payload = response.json()
    assert payload == {"detail": "Patient '999999' was not found."}


@pytest.mark.anyio("asyncio")
async def test_read_patient_context_with_selected_categories(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/patients/123456/context",
        params=[("categories", "labs"), ("categories", "careTeam")],
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["labResults"]
    assert payload["careTeam"]
    assert payload["medications"] == []
    assert payload["problems"] == []
    assert payload["plan"].startswith("Continue lisinopril")


@pytest.mark.anyio("asyncio")
async def test_read_patient_context_with_unknown_category(client: AsyncClient) -> None:
    response = await client.get(
        "/patients/123456/context",
        params={"categories": "unknown"},
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["demographics"]["patientId"] == "123456"
    assert payload["medications"] == []
    assert payload["labResults"] == []
    assert payload["plan"].startswith("Continue lisinopril")
