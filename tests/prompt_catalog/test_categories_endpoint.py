import sys
import types
from contextlib import contextmanager
from pathlib import Path
from typing import AsyncIterator, Iterator

import pytest
from httpx import ASGITransport, AsyncClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def _stub_logger_module(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """Provide a stub logger module so ``configure_logging`` is a no-op."""

    module_name = "shared.observability.logger"
    stub = types.ModuleType(module_name)

    class _DummyLogger:
        def bind(self, *args: object, **kwargs: object) -> "_DummyLogger":
            return self

        def info(self, *args: object, **kwargs: object) -> None:
            return None

        def warning(self, *args: object, **kwargs: object) -> None:
            return None

        def contextualize(self, *args: object, **kwargs: object):
            @contextmanager
            def _ctx():
                yield None

            return _ctx()

    def get_logger(name: str | None = None) -> _DummyLogger:
        return _DummyLogger()

    stub.get_logger = get_logger  # type: ignore[attr-defined]
    stub.configure_logging = lambda *args, **kwargs: None  # type: ignore[attr-defined]
    stub.generate_request_id = lambda: "test-request-id"  # type: ignore[attr-defined]
    stub.get_request_id = lambda: "test-request-id"  # type: ignore[attr-defined]

    @contextmanager
    def request_context(*args: object, **kwargs: object):
        yield "test-request-id"

    stub.request_context = request_context  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, module_name, stub)

    yield

    sys.modules.pop(module_name, None)


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    from services.prompt_catalog.app import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio("asyncio")
async def test_list_categories_returns_defaults(client: AsyncClient) -> None:
    from shared.llm.chains import DEFAULT_PROMPT_CATEGORIES

    response = await client.get("/categories")
    assert response.status_code == 200

    payload = response.json()
    expected = [category.as_dict() for category in DEFAULT_PROMPT_CATEGORIES]

    assert payload == expected


@pytest.mark.anyio("asyncio")
async def test_list_categories_schema(client: AsyncClient) -> None:
    response = await client.get("/categories")
    assert response.status_code == 200

    payload = response.json()
    assert isinstance(payload, list)

    for category in payload:
        assert set(category.keys()) == {"slug", "name", "description", "aliases"}
        assert isinstance(category["slug"], str)
        assert isinstance(category["name"], str)
        assert isinstance(category["description"], str)
        assert isinstance(category["aliases"], list)
        assert all(isinstance(alias, str) for alias in category["aliases"])
