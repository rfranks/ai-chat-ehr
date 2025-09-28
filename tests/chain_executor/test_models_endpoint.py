import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def anyio_backend() -> str:
    """Ensure anyio-powered tests execute against the asyncio backend."""

    return "asyncio"


async def _request_models_payload() -> dict:
    from services.chain_executor import app as chain_app

    transport = ASGITransport(app=chain_app.app)
    try:
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/chains/models")
    finally:
        await transport.aclose()

    assert response.status_code == 200
    return response.json()


@pytest.mark.anyio
async def test_models_endpoint_returns_all_specs() -> None:
    from services.chain_executor import app as chain_app
    from shared.llm.llmmodels import get_all_model_specs

    payload = await _request_models_payload()

    specs = get_all_model_specs()
    models = {entry["provider"]: entry for entry in payload["models"]}

    assert set(models) == {spec.provider.value for spec in specs}

    for spec in specs:
        entry = models[spec.provider.value]
        assert entry["canonical_name"] == spec.canonical_name
        assert entry["description"] == spec.description

    service = payload["service"]
    settings = chain_app.get_settings()

    assert service["name"] == chain_app.SERVICE_NAME
    assert service["default_model_provider"] == settings.default_model.provider
    assert service["default_model_name"] == settings.default_model.name


@pytest.mark.anyio
async def test_models_endpoint_preserves_alias_ordering() -> None:
    from shared.llm.llmmodels import get_all_model_specs

    payload = await _request_models_payload()

    models = {entry["provider"]: entry for entry in payload["models"]}

    for spec in get_all_model_specs():
        aliases = models[spec.provider.value]["aliases"]
        assert aliases == list(spec.aliases)
        if aliases:
            assert aliases[0] == spec.aliases[0]
