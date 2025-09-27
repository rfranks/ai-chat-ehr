"""Tests for :mod:`shared.llm.providers` behavior and edge cases."""

from __future__ import annotations

import importlib
import sys
import types
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def _stub_logger_module(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Provide a lightweight stand-in for the logger dependency used by providers."""

    module_name = "shared.observability.logger"
    stub = types.ModuleType(module_name)

    class _DummyLogger:
        def warning(
            self, *args: object, **kwargs: object
        ) -> None:  # pragma: no cover - stub
            return None

        def bind(
            self, *args: object, **kwargs: object
        ) -> "_DummyLogger":  # pragma: no cover - stub
            return self

        def contextualize(
            self, *args: object, **kwargs: object
        ):  # pragma: no cover - stub
            @contextmanager
            def _ctx() -> Generator[None, None, None]:
                yield None

            return _ctx()

    def get_logger(name: str | None = None) -> _DummyLogger:  # pragma: no cover - stub
        return _DummyLogger()

    stub.get_logger = get_logger  # type: ignore[attr-defined]
    stub.configure_logging = lambda *args, **kwargs: None  # type: ignore[attr-defined]
    stub.generate_request_id = lambda: "test-request-id"  # type: ignore[attr-defined]
    stub.get_request_id = lambda: None  # type: ignore[attr-defined]

    @contextmanager
    def request_context(
        *args, **kwargs
    ) -> Generator[str, None, None]:  # pragma: no cover - stub
        yield "test-request-id"

    stub.request_context = request_context  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, module_name, stub)

    try:
        yield
    finally:
        # Ensure subsequent imports in other tests can provide their own stubs if needed.
        sys.modules.pop(module_name, None)


@pytest.mark.parametrize(
    ("provider_name", "adapter_attr", "expected_model"),
    [
        ("OPENAI_GPT_35_TURBO", "openai_adapter", "gpt-3.5-turbo"),
        ("OPENAI_GPT_4O", "openai_adapter", "gpt-4o"),
        ("OPENAI_GPT_4O_MINI", "openai_adapter", "gpt-4o-mini"),
        ("AZURE_GPT_4O", "azure_adapter", "gpt-4o"),
        ("AZURE_GPT_4O_MINI", "azure_adapter", "gpt-4o-mini"),
        ("CLAUDE_3_HAIKU", "anthropic_adapter", "claude-3-haiku-20240307"),
        ("CLAUDE_3_SONNET", "anthropic_adapter", "claude-3-sonnet-20240229"),
        ("GEMINI_25_PRO", "vertex_adapter", "gemini-2.5-pro"),
        ("GEMINI_25_FLASH", "vertex_adapter", "gemini-2.5-flash"),
    ],
)
def test_create_client_dispatches_to_expected_adapter(
    provider_name: str,
    adapter_attr: str,
    expected_model: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    providers = importlib.import_module("shared.llm.providers")
    settings_module = importlib.import_module("shared.config.settings")

    provider = getattr(providers.LLMProvider, provider_name)
    adapter_module = getattr(providers, adapter_attr)

    model_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    model_cls = type(f"{provider_name}Model", (), {})

    def fake_get_chat_model(*args: object, **kwargs: object) -> object:
        model_calls.append((args, kwargs))
        return model_cls()

    monkeypatch.setattr(adapter_module, "get_chat_model", fake_get_chat_model)

    settings = settings_module.Settings()
    result = provider.create_client(settings=settings, temperature=0.42)

    assert isinstance(result, model_cls)
    assert model_calls, "Adapter was not invoked"

    called_args, called_kwargs = model_calls[-1]
    assert called_args[0] == expected_model

    expected_kwargs = {"settings": settings, "temperature": 0.42}
    if adapter_attr in {"azure_adapter", "vertex_adapter"}:
        expected_kwargs["has_explicit_model_override"] = False

    assert called_kwargs == expected_kwargs


def test_resolve_model_spec_defaults_to_openai_when_provider_missing() -> None:
    providers = importlib.import_module("shared.llm.providers")
    llmmodels = importlib.import_module("shared.llm.llmmodels")

    spec = llmmodels.resolve_model_spec(model_identifier=None, provider_hint=None)

    assert spec.provider is providers.LLMProvider.OPENAI_GPT_35_TURBO
    assert spec.model_name == "gpt-3.5-turbo"
    assert spec.canonical_name == providers.LLMProvider.OPENAI_GPT_35_TURBO.value


def test_resolve_model_spec_strips_double_colon_overrides() -> None:
    providers = importlib.import_module("shared.llm.providers")
    llmmodels = importlib.import_module("shared.llm.llmmodels")

    spec = llmmodels.resolve_model_spec(
        "azure::custom-deployment",
        provider_hint=providers.LLMProvider.AZURE_GPT_4O,
    )

    assert spec.provider is providers.LLMProvider.AZURE_GPT_4O
    assert spec.model_name == "custom-deployment"
    assert spec.canonical_name == "azure/custom-deployment"


def test_vertex_client_raises_when_env_credentials_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    providers = importlib.import_module("shared.llm.providers")
    settings_module = importlib.import_module("shared.config.settings")
    errors_module = importlib.import_module("shared.http.errors")

    missing_file = tmp_path / "missing-credentials.json"
    monkeypatch.setenv("VERTEX_PROJECT_ID", "test-project")
    monkeypatch.setenv("VERTEX_LOCATION", "us-central1")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(missing_file))
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

    settings = settings_module.Settings()

    provider = providers.LLMProvider.GEMINI_25_PRO

    with pytest.raises(errors_module.ProviderUnavailableError) as excinfo:
        provider.create_client(settings=settings)

    assert excinfo.value.provider == "vertex"
    assert excinfo.value.reason == "env_credentials_missing"
