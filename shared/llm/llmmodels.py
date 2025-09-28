"""Canonical model metadata and lookup helpers for language models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

from .providers import LLMProvider


@dataclass(frozen=True)
class ModelSpec:
    """Normalized metadata describing an LLM provider/model pairing."""

    provider: LLMProvider
    backend: str
    model_name: str
    canonical_name: str
    aliases: tuple[str, ...] = ()
    description: Optional[str] = None


DEFAULT_PROVIDER = LLMProvider.OPENAI_GPT_35_TURBO
DEFAULT_MODEL_PROVIDER = DEFAULT_PROVIDER
DEFAULT_CANONICAL_MODEL_NAME = DEFAULT_PROVIDER.value


_MODEL_SPECS: Dict[LLMProvider, ModelSpec] = {
    LLMProvider.OPENAI_GPT_35_TURBO: ModelSpec(
        provider=LLMProvider.OPENAI_GPT_35_TURBO,
        backend="openai",
        model_name="gpt-3.5-turbo",
        canonical_name=LLMProvider.OPENAI_GPT_35_TURBO.value,
        aliases=(
            "openai",
            "openai/gpt-3.5-turbo",
            "openai:gpt-3.5-turbo",
            "openai-gpt-3.5",
            "openai-gpt-3.5-turbo",
            "gpt-3.5",
            "gpt-3.5-turbo",
            "gpt-35",
            "gpt-35-turbo",
            "gpt35",
            "gpt3.5",
            "chatgpt",
            "default",
            "auto",
        ),
        description="OpenAI GPT-3.5 Turbo chat completion model.",
    ),
    LLMProvider.OPENAI_GPT_4O: ModelSpec(
        provider=LLMProvider.OPENAI_GPT_4O,
        backend="openai",
        model_name="gpt-4o",
        canonical_name=LLMProvider.OPENAI_GPT_4O.value,
        aliases=(
            "openai/gpt-4o",
            "openai:gpt-4o",
            "openai-gpt-4o",
            "openai-gpt4o",
            "gpt-4o",
            "gpt4o",
            "o4",
        ),
        description="OpenAI GPT-4o general-purpose multimodal model.",
    ),
    LLMProvider.OPENAI_GPT_4O_MINI: ModelSpec(
        provider=LLMProvider.OPENAI_GPT_4O_MINI,
        backend="openai",
        model_name="gpt-4o-mini",
        canonical_name=LLMProvider.OPENAI_GPT_4O_MINI.value,
        aliases=(
            "openai/gpt-4o-mini",
            "openai:gpt-4o-mini",
            "openai-gpt-4o-mini",
            "openai-gpt4o-mini",
            "gpt-4o-mini",
            "gpt4o-mini",
            "o4-mini",
            "openai-mini",
        ),
        description="OpenAI GPT-4o mini lightweight model.",
    ),
    LLMProvider.AZURE_GPT_4O: ModelSpec(
        provider=LLMProvider.AZURE_GPT_4O,
        backend="azure",
        model_name="gpt-4o",
        canonical_name=LLMProvider.AZURE_GPT_4O.value,
        aliases=(
            "azure",
            "azure-openai",
            "azure-openai/gpt-4o",
            "azure:gpt-4o",
            "azure/gpt-4o",
            "azure-gpt-4o",
            "azure-gpt4o",
            "gpt-4o-azure",
            "ms-azure",
            "microsoft-azure",
        ),
        description="Azure OpenAI GPT-4o deployment.",
    ),
    LLMProvider.AZURE_GPT_4O_MINI: ModelSpec(
        provider=LLMProvider.AZURE_GPT_4O_MINI,
        backend="azure",
        model_name="gpt-4o-mini",
        canonical_name=LLMProvider.AZURE_GPT_4O_MINI.value,
        aliases=(
            "azure-openai/gpt-4o-mini",
            "azure:gpt-4o-mini",
            "azure/gpt-4o-mini",
            "azure-gpt-4o-mini",
            "azure-gpt4o-mini",
            "gpt-4o-mini-azure",
        ),
        description="Azure OpenAI GPT-4o mini deployment.",
    ),
    LLMProvider.CLAUDE_3_HAIKU: ModelSpec(
        provider=LLMProvider.CLAUDE_3_HAIKU,
        backend="anthropic",
        model_name="claude-3-haiku-20240307",
        canonical_name=LLMProvider.CLAUDE_3_HAIKU.value,
        aliases=(
            "anthropic/claude-3-haiku",
            "anthropic:claude-3-haiku",
            "claude-3-haiku",
            "claude3-haiku",
            "claude-haiku",
            "anthropic-haiku",
            "haiku",
        ),
        description="Anthropic Claude 3 Haiku speedy model.",
    ),
    LLMProvider.CLAUDE_3_SONNET: ModelSpec(
        provider=LLMProvider.CLAUDE_3_SONNET,
        backend="anthropic",
        model_name="claude-3-sonnet-20240229",
        canonical_name=LLMProvider.CLAUDE_3_SONNET.value,
        aliases=(
            "anthropic/claude-3-sonnet",
            "anthropic:claude-3-sonnet",
            "claude-3-sonnet",
            "claude3-sonnet",
            "claude-sonnet",
            "sonnet",
            "anthropic",
            "claude",
        ),
        description="Anthropic Claude 3 Sonnet balanced capability model.",
    ),
    LLMProvider.GEMINI_25_PRO: ModelSpec(
        provider=LLMProvider.GEMINI_25_PRO,
        backend="vertex",
        model_name="gemini-2.5-pro",
        canonical_name=LLMProvider.GEMINI_25_PRO.value,
        aliases=(
            "vertex/gemini-2.5-pro",
            "vertex:gemini-2.5-pro",
            "google/gemini-2.5-pro",
            "gemini-2.5-pro",
            "gemini-pro",
            "gemini-pro-2.5",
            "vertex-ai-gemini-pro",
            "vertex-ai/gemini-pro",
            "vertex",
            "gemini",
            "google",
            "google-ai",
            "google-cloud",
        ),
        description="Google Gemini 2.5 Pro on Vertex AI.",
    ),
    LLMProvider.GEMINI_25_FLASH: ModelSpec(
        provider=LLMProvider.GEMINI_25_FLASH,
        backend="vertex",
        model_name="gemini-2.5-flash",
        canonical_name=LLMProvider.GEMINI_25_FLASH.value,
        aliases=(
            "vertex/gemini-2.5-flash",
            "vertex:gemini-2.5-flash",
            "google/gemini-2.5-flash",
            "gemini-2.5-flash",
            "gemini-flash",
            "gemini-flash-2.5",
            "vertex-ai-gemini-flash",
        ),
        description="Google Gemini 2.5 Flash fast model on Vertex AI.",
    ),
}


_ALIAS_TO_PROVIDER: Dict[str, LLMProvider] = {}
_BACKEND_ALIAS_TO_PROVIDER: Dict[str, LLMProvider] = {}


def _normalize_alias(text: str) -> str:
    cleaned = text.strip().lower()
    cleaned = cleaned.replace("\\", "/")
    cleaned = cleaned.replace("::", "/").replace(":", "/")
    cleaned = cleaned.replace(" ", "")
    cleaned = cleaned.replace("__", "_").replace("_", "-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    while "//" in cleaned:
        cleaned = cleaned.replace("//", "/")
    return cleaned


def _register_alias(provider: LLMProvider, alias: str) -> None:
    key = _normalize_alias(alias)
    if not key:
        return
    _ALIAS_TO_PROVIDER.setdefault(key, provider)


def _register_backend_alias(alias: str, provider: LLMProvider) -> None:
    key = _normalize_alias(alias)
    if not key:
        return
    _BACKEND_ALIAS_TO_PROVIDER.setdefault(key, provider)


def _iter_aliases(provider: LLMProvider, spec: ModelSpec) -> Iterable[str]:
    yield spec.canonical_name
    yield provider.value
    yield provider.value.replace("/", "-")
    yield provider.value.replace("/", ":")
    provider_name = provider.name.lower()
    yield provider_name
    yield provider_name.replace("_", "-")
    yield spec.canonical_name.replace("/", "-")
    yield spec.canonical_name.replace("/", ":")
    for alias in spec.aliases:
        yield alias


for provider, spec in _MODEL_SPECS.items():
    for alias in _iter_aliases(provider, spec):
        _register_alias(provider, alias)

_register_backend_alias("openai", LLMProvider.OPENAI_GPT_35_TURBO)
_register_backend_alias("oai", LLMProvider.OPENAI_GPT_35_TURBO)
_register_backend_alias("azure", LLMProvider.AZURE_GPT_4O)
_register_backend_alias("azure-openai", LLMProvider.AZURE_GPT_4O)
_register_backend_alias("ms-azure", LLMProvider.AZURE_GPT_4O)
_register_backend_alias("microsoft", LLMProvider.AZURE_GPT_4O)
_register_backend_alias("anthropic", LLMProvider.CLAUDE_3_SONNET)
_register_backend_alias("claude", LLMProvider.CLAUDE_3_SONNET)
_register_backend_alias("vertex", LLMProvider.GEMINI_25_PRO)
_register_backend_alias("vertex-ai", LLMProvider.GEMINI_25_PRO)
_register_backend_alias("gemini", LLMProvider.GEMINI_25_PRO)
_register_backend_alias("google", LLMProvider.GEMINI_25_PRO)
_register_backend_alias("google-ai", LLMProvider.GEMINI_25_PRO)
_register_backend_alias("google-cloud", LLMProvider.GEMINI_25_PRO)


def available_model_specs() -> Tuple[ModelSpec, ...]:
    """Return the known model specifications."""

    return tuple(_MODEL_SPECS.values())


def get_model_spec(provider: LLMProvider) -> ModelSpec:
    """Return the canonical :class:`ModelSpec` for ``provider``."""

    return _MODEL_SPECS[provider]


def _split_backend(identifier: str) -> Tuple[Optional[str], Optional[str]]:
    if "/" not in identifier:
        return None, None
    backend, remainder = identifier.split("/", 1)
    return backend or None, remainder or None


def _extract_model_override(raw_identifier: str) -> str:
    candidate = raw_identifier.strip()
    for token in ("::", "/", ":"):
        if token in candidate:
            candidate = candidate.split(token, 1)[1]
            break
    candidate = candidate.strip()
    return candidate or raw_identifier.strip()


def _canonicalize_name(backend: str, model_name: str, fallback: str) -> str:
    normalized_backend = _normalize_alias(backend) or backend
    normalized_model = _normalize_alias(model_name)
    if not normalized_model:
        normalized_model = _normalize_alias(fallback) or fallback
    if "/" in normalized_model:
        normalized_model = normalized_model.split("/", 1)[-1]
    return f"{normalized_backend}/{normalized_model}"


def resolve_model_spec(
    model_identifier: Optional[str],
    *,
    provider_hint: Optional[LLMProvider] = None,
) -> ModelSpec:
    """Resolve ``model_identifier`` into a canonical :class:`ModelSpec`."""

    if model_identifier:
        raw_identifier = model_identifier.strip()
        normalized = _normalize_alias(raw_identifier)
        if normalized:
            provider = _ALIAS_TO_PROVIDER.get(normalized)
            if provider is not None:
                return _MODEL_SPECS[provider]

            backend_alias, remainder = _split_backend(normalized)
            if backend_alias:
                backend_provider = _BACKEND_ALIAS_TO_PROVIDER.get(backend_alias)
                if backend_provider is not None:
                    base_spec = _MODEL_SPECS[backend_provider]
                    override_model = _extract_model_override(raw_identifier)
                    canonical = _canonicalize_name(
                        base_spec.backend, override_model, base_spec.model_name
                    )
                    return ModelSpec(
                        provider=backend_provider,
                        backend=base_spec.backend,
                        model_name=override_model or base_spec.model_name,
                        canonical_name=canonical,
                        aliases=base_spec.aliases,
                        description=base_spec.description,
                    )

        if provider_hint is not None:
            base_spec = _MODEL_SPECS[provider_hint]
            override_model = _extract_model_override(raw_identifier)
            canonical = _canonicalize_name(
                base_spec.backend, override_model, base_spec.model_name
            )
            return ModelSpec(
                provider=provider_hint,
                backend=base_spec.backend,
                model_name=override_model or base_spec.model_name,
                canonical_name=canonical,
                aliases=base_spec.aliases,
                description=base_spec.description,
            )

    if provider_hint is not None:
        return _MODEL_SPECS[provider_hint]

    return _MODEL_SPECS[DEFAULT_PROVIDER]


def canonical_model_name(
    model_identifier: Optional[str],
    *,
    provider_hint: Optional[LLMProvider] = None,
) -> str:
    """Return the canonical name for ``model_identifier``."""

    return resolve_model_spec(
        model_identifier, provider_hint=provider_hint
    ).canonical_name


def resolve_provider(
    model_identifier: Optional[str],
    *,
    provider_hint: Optional[LLMProvider] = None,
) -> LLMProvider:
    """Return the :class:`LLMProvider` for ``model_identifier``."""

    return resolve_model_spec(model_identifier, provider_hint=provider_hint).provider


def resolve_model_name(
    model_identifier: Optional[str],
    *,
    provider_hint: Optional[LLMProvider] = None,
) -> str:
    """Return the provider-specific model identifier for ``model_identifier``."""

    return resolve_model_spec(model_identifier, provider_hint=provider_hint).model_name


__all__ = [
    "ModelSpec",
    "DEFAULT_PROVIDER",
    "DEFAULT_MODEL_PROVIDER",
    "DEFAULT_CANONICAL_MODEL_NAME",
    "available_model_specs",
    "canonical_model_name",
    "get_model_spec",
    "resolve_model_name",
    "resolve_model_spec",
    "resolve_provider",
]
