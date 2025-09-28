from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import cast

import httpx
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

chain_executor_app = importlib.import_module("services.chain_executor.app")
PatientContextClient = chain_executor_app.PatientContextClient
PatientContextServiceError = chain_executor_app.PatientContextServiceError
PatientNotFoundError = chain_executor_app.PatientNotFoundError


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _DummyResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:  # pragma: no cover - trivial stub
        return None

    def json(self) -> dict[str, object]:  # pragma: no cover - trivial stub
        return self._payload


class _DummyHttpClient:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    async def get(self, url: str, params: object = None) -> _DummyResponse:
        self.requests.append({"url": url, "params": params})
        return _DummyResponse({})


class _NotFoundHttpClient:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    async def get(self, url: str, params: object = None) -> _DummyResponse:
        self.requests.append({"url": url, "params": params})
        request = httpx.Request("GET", f"http://patient-context{url}")
        response = httpx.Response(status_code=404, request=request)
        raise httpx.HTTPStatusError("Not found", request=request, response=response)


class _ErrorHttpClient:
    def __init__(self, exc: httpx.HTTPError) -> None:
        self._exc = exc
        self.requests: list[dict[str, object]] = []

    async def get(self, url: str, params: object = None) -> _DummyResponse:
        self.requests.append({"url": url, "params": params})
        raise self._exc


@pytest.mark.anyio("asyncio")
async def test_patient_context_client_strips_patient_identifier_whitespace() -> None:
    http_client = _DummyHttpClient()
    typed_client = cast(httpx.AsyncClient, http_client)
    client = PatientContextClient(typed_client)

    await client.get_patient_context("  patient-123  ", categories=["labs", "notes"])

    assert http_client.requests == [
        {
            "url": "/patients/patient-123/context",
            "params": [("categories", "labs"), ("categories", "notes")],
        }
    ]


@pytest.mark.anyio("asyncio")
async def test_patient_context_client_rejects_empty_patient_identifier() -> None:
    http_client = _DummyHttpClient()
    typed_client = cast(httpx.AsyncClient, http_client)
    client = PatientContextClient(typed_client)

    with pytest.raises(PatientContextServiceError, match="cannot be empty"):
        await client.get_patient_context("   ")


@pytest.mark.anyio("asyncio")
async def test_patient_context_client_raises_not_found_for_missing_patient() -> None:
    http_client = _NotFoundHttpClient()
    typed_client = cast(httpx.AsyncClient, http_client)
    client = PatientContextClient(typed_client)

    with pytest.raises(PatientNotFoundError) as exc_info:
        await client.get_patient_context("patient-404")

    assert exc_info.value.patient_id == "patient-404"
    assert http_client.requests == [
        {"url": "/patients/patient-404/context", "params": None}
    ]


@pytest.mark.anyio("asyncio")
async def test_patient_context_client_wraps_generic_http_errors() -> None:
    error = httpx.HTTPError("network down")
    http_client = _ErrorHttpClient(error)
    typed_client = cast(httpx.AsyncClient, http_client)
    client = PatientContextClient(typed_client)

    with pytest.raises(PatientContextServiceError) as exc_info:
        await client.get_patient_context("patient-500")

    assert exc_info.value.__cause__ is error
    assert http_client.requests == [
        {"url": "/patients/patient-500/context", "params": None}
    ]
