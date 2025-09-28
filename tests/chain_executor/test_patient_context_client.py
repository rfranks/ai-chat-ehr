from __future__ import annotations

from typing import cast

import httpx
import pytest

from services.chain_executor.app import (
    PatientContextClient,
    PatientContextServiceError,
    PatientNotFoundError,
)


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
        self.requested_urls: list[str] = []

    async def get(self, url: str) -> _DummyResponse:
        self.requested_urls.append(url)
        return _DummyResponse({})


class _NotFoundHttpClient:
    def __init__(self) -> None:
        self.requested_urls: list[str] = []

    async def get(self, url: str) -> _DummyResponse:
        self.requested_urls.append(url)
        request = httpx.Request("GET", f"http://patient-context{url}")
        response = httpx.Response(status_code=404, request=request)
        raise httpx.HTTPStatusError("Not found", request=request, response=response)


class _ErrorHttpClient:
    def __init__(self, exc: httpx.HTTPError) -> None:
        self._exc = exc
        self.requested_urls: list[str] = []

    async def get(self, url: str) -> _DummyResponse:
        self.requested_urls.append(url)
        raise self._exc


@pytest.mark.anyio("asyncio")
async def test_patient_context_client_strips_patient_identifier_whitespace() -> None:
    http_client = _DummyHttpClient()
    typed_client = cast(httpx.AsyncClient, http_client)
    client = PatientContextClient(typed_client)

    await client.get_patient_context("  patient-123  ")

    assert http_client.requested_urls == ["/patients/patient-123/context"]


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
    assert http_client.requested_urls == ["/patients/patient-404/context"]


@pytest.mark.anyio("asyncio")
async def test_patient_context_client_wraps_generic_http_errors() -> None:
    error = httpx.HTTPError("network down")
    http_client = _ErrorHttpClient(error)
    typed_client = cast(httpx.AsyncClient, http_client)
    client = PatientContextClient(typed_client)

    with pytest.raises(PatientContextServiceError) as exc_info:
        await client.get_patient_context("patient-500")

    assert exc_info.value.__cause__ is error
    assert http_client.requested_urls == ["/patients/patient-500/context"]
