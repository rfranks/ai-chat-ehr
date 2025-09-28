from __future__ import annotations

import pytest

from services.chain_executor.app import PatientContextClient


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


@pytest.mark.anyio("asyncio")
async def test_patient_context_client_strips_patient_identifier_whitespace() -> None:
    http_client = _DummyHttpClient()
    client = PatientContextClient(http_client)

    await client.get_patient_context("  patient-123  ")

    assert http_client.requested_urls == ["/patients/patient-123/context"]
