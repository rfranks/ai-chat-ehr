"""FastAPI application orchestrating prompt chain execution."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, AsyncIterator, Iterable, Mapping, Sequence, cast

import httpx
from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from fastapi.responses import StreamingResponse
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_core.messages import AIMessage, AIMessageChunk
from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.config.settings import Settings, get_settings
from shared.llm import (
    DEFAULT_MODEL_PROVIDER,
    InvalidPromptTemplateError,
    MissingPromptTemplateError,
    ModelSpec,
    PromptTemplateSpec,
    PromptVariableMismatchError,
    build_context_variables,
    build_prompt_template,
    resolve_model_spec,
    resolve_provider,
)
from shared.llm.providers import LLMProvider
from shared.llm.chains import (
    CategoryClassifier,
    DEFAULT_PROMPT_CATEGORIES,
    ModelClassifier,
)
from shared.models.chain import (
    ChainExecutionRequest,
    ChainExecutionResponse,
    ChainStepResult,
)
from shared.models.chat import (
    ChatPrompt,
    ChatPromptKey,
    EHRPatientContext,
    PromptChainItem,
)
from shared.http.errors import (
    ProblemDetailsException,
    PromptNotFoundError,
    register_exception_handlers,
)
from shared.observability.logger import configure_logging, get_logger
from shared.observability.middleware import (
    CorrelationIdMiddleware,
    RequestTimingMiddleware,
)

SERVICE_NAME = "chain_executor"

configure_logging(service_name=SERVICE_NAME)

app = FastAPI(title="Chain Executor Service")
router = APIRouter(prefix="/chains", tags=["chains"])

app.add_middleware(RequestTimingMiddleware)
app.add_middleware(CorrelationIdMiddleware)
register_exception_handlers(app)

logger = get_logger(__name__)


class ChainExecutorSettings(BaseSettings):
    """Configuration for interacting with upstream services."""

    prompt_catalog_url: AnyHttpUrl = Field(
        default=cast(AnyHttpUrl, "http://localhost:8001"),
        description="Base URL for the prompt catalog service",
    )
    patient_context_url: AnyHttpUrl = Field(
        default=cast(AnyHttpUrl, "http://localhost:8002"),
        description="Base URL for the patient context service",
    )
    http_timeout: float = Field(
        default=10.0,
        ge=1.0,
        description="Timeout in seconds for outbound HTTP requests",
    )

    model_config = SettingsConfigDict(
        env_prefix="CHAIN_EXECUTOR_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache
def get_service_settings() -> ChainExecutorSettings:
    """Return cached chain executor settings."""

    return ChainExecutorSettings()


_prompt_http_client: httpx.AsyncClient | None = None
_context_http_client: httpx.AsyncClient | None = None


def _strip_trailing_slash(url: str) -> str:
    return url[:-1] if url.endswith("/") else url


def _create_http_client(base_url: str, timeout: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=_strip_trailing_slash(base_url), timeout=timeout)


async def get_prompt_http_client(
    settings: ChainExecutorSettings = Depends(get_service_settings),
) -> httpx.AsyncClient:
    """Return a shared HTTP client for the prompt catalog service."""

    global _prompt_http_client
    if _prompt_http_client is None:
        _prompt_http_client = _create_http_client(
            str(settings.prompt_catalog_url), settings.http_timeout
        )
    return _prompt_http_client


async def get_patient_http_client(
    settings: ChainExecutorSettings = Depends(get_service_settings),
) -> httpx.AsyncClient:
    """Return a shared HTTP client for the patient context service."""

    global _context_http_client
    if _context_http_client is None:
        _context_http_client = _create_http_client(
            str(settings.patient_context_url), settings.http_timeout
        )
    return _context_http_client


class PromptCatalogServiceError(RuntimeError):
    """Raised when the prompt catalog service cannot satisfy a request."""


class PatientContextServiceError(RuntimeError):
    """Raised when the patient context service fails to respond."""


class PatientNotFoundError(PatientContextServiceError):
    """Raised when the requested patient identifier cannot be located."""

    def __init__(self, patient_id: str) -> None:
        super().__init__(f"Patient '{patient_id}' was not found.")
        self.patient_id = patient_id


class PromptCatalogClient:
    """Thin HTTP client wrapper for the prompt catalog service."""

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._http = http_client

    async def get_prompt(self, identifier: ChatPromptKey | str) -> ChatPrompt:
        prompt_id = (
            identifier.value
            if isinstance(identifier, ChatPromptKey)
            else str(identifier).strip()
        )
        if not prompt_id:
            raise PromptCatalogServiceError("Prompt identifier cannot be empty")

        try:
            response = await self._http.get(f"/prompts/{prompt_id}")
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:  # pragma: no cover - network failure
            if exc.response.status_code == status.HTTP_404_NOT_FOUND:
                raise PromptNotFoundError(prompt_id) from exc
            raise PromptCatalogServiceError(
                f"Prompt catalog request failed with status {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:  # pragma: no cover - network failure
            raise PromptCatalogServiceError("Prompt catalog request failed") from exc

        payload = response.json()
        if "prompt" not in payload:
            raise PromptCatalogServiceError(
                "Prompt catalog response missing 'prompt' field"
            )
        return ChatPrompt.model_validate(payload["prompt"])


class PatientContextClient:
    """HTTP client wrapper for retrieving patient context payloads."""

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._http = http_client

    async def get_patient_context(
        self, patient_id: str, *, categories: Sequence[str] | None = None
    ) -> EHRPatientContext:
        normalized = patient_id.strip()
        if not normalized:
            raise PatientContextServiceError("Patient identifier cannot be empty")

        params: httpx.QueryParams | None = None
        if categories:
            params = httpx.QueryParams(
                [("categories", slug) for slug in categories if slug]
            )

        try:
            response = await self._http.get(
                f"/patients/{normalized}/context", params=params
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:  # pragma: no cover - network failure
            if exc.response.status_code == status.HTTP_404_NOT_FOUND:
                raise PatientNotFoundError(normalized) from exc
            raise PatientContextServiceError(
                f"Patient context request failed with status {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:  # pragma: no cover - network failure
            raise PatientContextServiceError("Patient context request failed") from exc

        return EHRPatientContext.model_validate(response.json())


async def get_prompt_catalog_client(
    http_client: httpx.AsyncClient = Depends(get_prompt_http_client),
) -> PromptCatalogClient:
    """Return a client for interacting with the prompt catalog service."""

    return PromptCatalogClient(http_client)


async def get_patient_context_client(
    http_client: httpx.AsyncClient = Depends(get_patient_http_client),
) -> PatientContextClient:
    """Return a client for retrieving patient context payloads."""

    return PatientContextClient(http_client)


@app.on_event("shutdown")
async def shutdown_clients() -> None:  # pragma: no cover - app lifecycle management
    """Close shared HTTP clients when the application shuts down."""

    global _prompt_http_client, _context_http_client
    if _prompt_http_client is not None:
        await _prompt_http_client.aclose()
        _prompt_http_client = None
    if _context_http_client is not None:
        await _context_http_client.aclose()
        _context_http_client = None


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Return a simple health payload for orchestration checks."""

    return {"status": "ok", "service": SERVICE_NAME}


@dataclass
class _ResolvedPrompt:
    prompt: ChatPrompt
    template: PromptTemplate
    input_variables: Sequence[str]
    output_key: str


@dataclass
class _ChainExecutionContext:
    payload: ChainExecutionRequest
    llm: Any
    model_spec: ModelSpec
    provider: LLMProvider
    patient_context: EHRPatientContext | None
    variables: dict[str, Any]
    steps: list[ChainStepResult]
    resolved_prompts: list[_ResolvedPrompt]


_CATEGORY_CLASSIFICATION_CACHE: dict[str, tuple[str, ...]] = {}
_KNOWN_CATEGORY_SLUGS: frozenset[str] = frozenset(
    category.slug for category in DEFAULT_PROMPT_CATEGORIES
)


def _filter_valid_categories(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        slug = value.strip()
        if not slug:
            continue
        if slug not in _KNOWN_CATEGORY_SLUGS:
            continue
        if slug in seen:
            continue
        seen.add(slug)
        ordered.append(slug)
    return ordered


def _normalize_category_source(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        slug = value.strip()
        return [slug] if slug else []
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, str)):
        collected: list[str] = []
        for item in value:
            if isinstance(item, str):
                slug = item.strip()
                if slug:
                    collected.append(slug)
        return collected
    return []


def _get_prompt_categories(prompt: ChatPrompt) -> list[str]:
    categories: list[str] = []
    direct = getattr(prompt, "categories", None)
    categories.extend(_normalize_category_source(direct))
    if isinstance(prompt.metadata, Mapping):
        categories.extend(_normalize_category_source(prompt.metadata.get("categories")))
    return _filter_valid_categories(categories)


def _set_prompt_categories(prompt: ChatPrompt, categories: Iterable[str]) -> None:
    normalized = _filter_valid_categories(categories)
    if hasattr(prompt, "categories"):
        try:
            setattr(prompt, "categories", list(normalized))
        except Exception:  # pragma: no cover - defensive mutation guard
            pass
    if isinstance(prompt.metadata, Mapping):
        if isinstance(prompt.metadata, dict):
            prompt.metadata["categories"] = list(normalized)
        else:
            updated = dict(prompt.metadata)
            updated["categories"] = list(normalized)
            prompt.metadata = updated  # type: ignore[assignment]
    else:
        prompt.metadata = {"categories": list(normalized)}


def _category_cache_key(prompt: ChatPrompt) -> str:
    parts: list[str] = []
    if isinstance(prompt.metadata, Mapping):
        identifier = prompt.metadata.get("id") or prompt.metadata.get("identifier")
        if identifier:
            parts.append(f"id:{identifier}")
    if isinstance(prompt.key, ChatPromptKey):
        parts.append(f"key:{prompt.key.value}")
    elif prompt.key:
        parts.append(f"key:{prompt.key}")
    if prompt.title:
        parts.append(f"title:{prompt.title}")
    if prompt.template:
        digest = hashlib.sha1(prompt.template.strip().encode("utf-8")).hexdigest()
        parts.append(f"template:{digest}")
    if prompt.description:
        digest = hashlib.sha1(prompt.description.strip().encode("utf-8")).hexdigest()
        parts.append(f"description:{digest}")
    if not parts:
        payload = prompt.model_dump(mode="json", by_alias=True, exclude_none=True)
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha1(serialized.encode("utf-8")).hexdigest()
        parts.append(f"payload:{digest}")
    return "|".join(str(part) for part in parts if part)


async def _ensure_prompt_categories(
    prompt: ChatPrompt,
    llm: Any,
    classifier: CategoryClassifier | None,
) -> CategoryClassifier | None:
    existing = _get_prompt_categories(prompt)
    if existing:
        _set_prompt_categories(prompt, existing)
        return classifier

    cache_key = _category_cache_key(prompt)
    cached = _CATEGORY_CLASSIFICATION_CACHE.get(cache_key)
    if cached is not None:
        _set_prompt_categories(prompt, cached)
        return classifier

    classifier = classifier or CategoryClassifier.create(llm)

    prompt_payload = prompt.model_dump(mode="json", by_alias=True, exclude_none=True)
    prompt_json = json.dumps(prompt_payload, ensure_ascii=False, indent=2)

    try:
        chain = classifier.chain
        ainvoke = getattr(chain, "ainvoke", None)
        if callable(ainvoke):
            result = await ainvoke({"prompt_json": prompt_json})
        else:  # pragma: no cover - legacy synchronous chains
            result = await asyncio.to_thread(chain.invoke, {"prompt_json": prompt_json})
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning(
            "prompt_category_classification_failed",
            error=str(exc),
            exc_info=True,
        )
        return classifier

    output_key = getattr(classifier.chain, "output_key", "text")
    raw_output: str
    if isinstance(result, Mapping):
        raw_output = str(result.get(output_key) or result.get("text") or "")
    else:
        raw_output = str(result)

    categories = tuple(classifier.parse_response(raw_output))
    _CATEGORY_CLASSIFICATION_CACHE[cache_key] = categories
    _set_prompt_categories(prompt, categories)
    return classifier


def _coerce_provider(value: Any) -> LLMProvider | None:
    if isinstance(value, LLMProvider):
        return value
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return None
        try:
            return LLMProvider(candidate)
        except ValueError:
            pass
        normalized = candidate.lower()
        for provider in LLMProvider:
            variants = {
                provider.value.lower(),
                provider.value.replace("/", "-").lower(),
                provider.value.replace("/", ":").lower(),
                provider.name.lower(),
            }
            if normalized in variants:
                return provider
        try:
            spec = resolve_model_spec(candidate)
        except Exception:  # pragma: no cover - defensive
            return None
        alias_candidates = {
            spec.provider.value.lower(),
            spec.canonical_name.lower(),
            spec.model_name.lower(),
            spec.provider.name.lower(),
        }
        alias_candidates.update(alias.lower() for alias in spec.aliases)
        normalized_variants = set(alias_candidates)
        for alias in list(alias_candidates):
            normalized_variants.add(alias.replace("/", "-"))
            normalized_variants.add(alias.replace("/", ":"))
        if normalized in normalized_variants:
            return spec.provider
        if normalized.replace("/", "-") in normalized_variants:
            return spec.provider
    return None


def _extract_prompt_model_preferences(
    prompt: ChatPrompt,
) -> tuple[str | None, LLMProvider | None]:
    if not isinstance(prompt.metadata, Mapping):
        return None, None

    metadata = prompt.metadata
    model_identifier: str | None = None
    provider_hint: LLMProvider | None = None

    model_fields = ("model", "model_name", "modelName")
    for field in model_fields:
        value = metadata.get(field)
        if isinstance(value, str):
            candidate = value.strip()
            if candidate:
                model_identifier = candidate
                break
        elif isinstance(value, Mapping):
            nested = value.get("id") or value.get("slug") or value.get("name")
            if isinstance(nested, str):
                candidate = nested.strip()
                if candidate:
                    model_identifier = candidate
                    break

    provider_fields = ("model_provider", "modelProvider", "provider", "llm", "engine")
    for field in provider_fields:
        value = metadata.get(field)
        provider_hint = _coerce_provider(value)
        if provider_hint is not None:
            break

    return model_identifier, provider_hint


async def _classify_model_slug(prompt: ChatPrompt, settings: Settings) -> str | None:
    try:
        classifier_llm = DEFAULT_MODEL_PROVIDER.create_client(settings=settings)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning(
            "prompt_model_classifier_initialization_failed",
            error=str(exc),
            exc_info=True,
        )
        return None

    try:
        classifier = ModelClassifier.create(classifier_llm)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning(
            "prompt_model_classifier_creation_failed",
            error=str(exc),
            exc_info=True,
        )
        return None

    prompt_payload = prompt.model_dump(mode="json", by_alias=True, exclude_none=True)
    prompt_json = json.dumps(prompt_payload, ensure_ascii=False, indent=2)

    try:
        chain = classifier.chain
        ainvoke = getattr(chain, "ainvoke", None)
        if callable(ainvoke):
            result = await ainvoke({"prompt_json": prompt_json})
        else:  # pragma: no cover - legacy synchronous chains
            result = await asyncio.to_thread(chain.invoke, {"prompt_json": prompt_json})
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning(
            "prompt_model_classification_failed",
            error=str(exc),
            exc_info=True,
        )
        return None

    output_key = getattr(classifier.chain, "output_key", "text")
    raw_output: str
    if isinstance(result, Mapping):
        raw_output = str(result.get(output_key) or result.get("text") or "")
    else:
        raw_output = str(result)

    return classifier.parse_response(raw_output)


_OUTPUT_KEY_SANITIZER = re.compile(r"[^0-9a-zA-Z]+")


def _slugify(text: str) -> str:
    candidate = _OUTPUT_KEY_SANITIZER.sub("_", text.strip().lower())
    return candidate.strip("_")


def _describe_prompt(prompt: ChatPrompt) -> str:
    if isinstance(prompt.key, ChatPromptKey):
        return prompt.key.value
    if prompt.key:
        return str(prompt.key)
    if prompt.title:
        return prompt.title
    if prompt.template:
        snippet = prompt.template.strip().splitlines()
        if snippet:
            head = snippet[0]
            return head if len(head) <= 48 else f"{head[:45]}..."
    return "prompt"


def _determine_output_key(
    prompt: ChatPrompt,
    index: int,
    used: set[str],
) -> str:
    candidates: list[str] = []
    metadata_key = None
    if isinstance(prompt.metadata, Mapping):
        metadata_key = prompt.metadata.get("output_key")
    if isinstance(metadata_key, str):
        candidates.append(metadata_key)
    if isinstance(prompt.key, ChatPromptKey):
        candidates.append(prompt.key.value)
    elif prompt.key:
        candidates.append(str(prompt.key))
    if prompt.title:
        candidates.append(prompt.title)

    for candidate in candidates:
        slug = _slugify(candidate)
        if slug and slug not in used:
            used.add(slug)
            return slug

    base = f"step_{index + 1}"
    candidate = base
    counter = 1
    while candidate in used:
        candidate = f"{base}_{counter}"
        counter += 1
    used.add(candidate)
    return candidate


async def _resolve_prompt(
    item: PromptChainItem,
    prompt_client: PromptCatalogClient,
) -> ChatPrompt:
    if isinstance(item, ChatPrompt):
        return item
    if isinstance(item, ChatPromptKey):
        return await prompt_client.get_prompt(item)
    if isinstance(item, str):
        return ChatPrompt(template=item)
    raise TypeError(f"Unsupported prompt chain item type: {type(item)!r}")


def _prepare_prompt(
    prompt: ChatPrompt, index: int, available: set[str], used_keys: set[str]
) -> _ResolvedPrompt:
    try:
        spec: PromptTemplateSpec = build_prompt_template(prompt)
    except MissingPromptTemplateError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Prompt '{_describe_prompt(prompt)}' does not define template text.",
        ) from exc
    except InvalidPromptTemplateError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Prompt '{_describe_prompt(prompt)}' contains an invalid template: {exc}"
            ),
        ) from exc
    except PromptVariableMismatchError as exc:
        missing = ", ".join(sorted(exc.missing_variables))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Prompt '{_describe_prompt(prompt)}' declares input variable(s) {missing} "
                "that are not present in the template."
            ),
        ) from exc

    input_variables = list(spec.input_variables)
    missing_inputs = [name for name in input_variables if name not in available]
    if missing_inputs:
        formatted = ", ".join(missing_inputs)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Prompt '{_describe_prompt(prompt)}' requires input variable(s) {formatted} "
                "that were not provided by prior steps or request variables."
            ),
        )

    output_key = _determine_output_key(prompt, index, used_keys)
    return _ResolvedPrompt(
        prompt=prompt,
        template=spec.template,
        input_variables=input_variables,
        output_key=output_key,
    )


def _apply_model_overrides(
    llm: Any, *, max_tokens: int | None, top_p: float | None
) -> None:
    if max_tokens is None and top_p is None:
        return

    kwargs: dict[str, Any] = {}
    if hasattr(llm, "model_kwargs"):
        existing = getattr(llm, "model_kwargs")
        if isinstance(existing, Mapping):
            kwargs.update(existing)
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
        if hasattr(llm, "max_tokens"):
            try:
                setattr(llm, "max_tokens", max_tokens)
            except Exception:  # pragma: no cover - defensive
                pass
    if top_p is not None:
        kwargs["top_p"] = top_p
        if hasattr(llm, "top_p"):
            try:
                setattr(llm, "top_p", top_p)
            except Exception:  # pragma: no cover - defensive
                pass
    if kwargs and hasattr(llm, "model_kwargs"):
        setattr(llm, "model_kwargs", kwargs)


def _normalize_outputs(outputs: Mapping[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in outputs.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            normalized[key] = value
        else:
            normalized[key] = str(value)
    return normalized


def _create_llm_chain(resolved: _ResolvedPrompt, llm: Any) -> LLMChain:
    return LLMChain(llm=llm, prompt=resolved.template, output_key=resolved.output_key)


async def _invoke_llm_chain(
    chain: LLMChain, variables: Mapping[str, Any]
) -> Mapping[str, Any]:
    ainvoke = getattr(chain, "ainvoke", None)
    if callable(ainvoke):
        return await ainvoke(variables)
    return await asyncio.to_thread(chain.invoke, variables)


def _coalesce_text(payload: Any) -> str:
    if payload is None:
        return ""
    if isinstance(payload, AIMessageChunk):
        text = _coalesce_text(payload.content)
        if text:
            return text
        return _coalesce_text(payload.additional_kwargs)
    if isinstance(payload, AIMessage):
        text = _coalesce_text(payload.content)
        if text:
            return text
        return _coalesce_text(payload.additional_kwargs)
    if isinstance(payload, str):
        return payload
    if isinstance(payload, Mapping):
        candidates = []
        for key in ("text", "content", "message", "value", "output"):
            if key in payload:
                candidates.append(payload[key])
        if "delta" in payload:
            candidates.append(payload["delta"])
        if "choices" in payload:
            candidates.append(payload["choices"])
        for candidate in candidates:
            text = _coalesce_text(candidate)
            if text:
                return text
        return ""
    if isinstance(payload, Iterable) and not isinstance(
        payload, (bytes, bytearray, str)
    ):
        parts: list[str] = []
        for item in payload:
            text = _coalesce_text(item)
            if text:
                parts.append(text)
        return "".join(parts)
    return str(payload)


def _format_sse_event(payload: Mapping[str, Any]) -> str:
    event_type = str(payload.get("type", "message"))
    serialized = json.dumps(payload, ensure_ascii=False)
    lines = serialized.splitlines() or [serialized]
    buffer: list[str] = [f"event: {event_type}\n"]
    for line in lines:
        buffer.append(f"data: {line}\n")
    buffer.append("\n")
    return "".join(buffer)


def _finalize_response(
    context: _ChainExecutionContext,
    *,
    variables: Mapping[str, Any],
    outputs: Mapping[str, Any],
) -> ChainExecutionResponse:
    final_outputs = dict(outputs)
    final_variables = dict(variables)
    final_output_key = (
        context.resolved_prompts[-1].output_key if context.resolved_prompts else None
    )
    final_output = final_outputs.get(final_output_key) if final_output_key else None
    metadata = dict(context.payload.metadata)
    metadata.setdefault("service", SERVICE_NAME)
    metadata.setdefault("canonical_model", context.model_spec.canonical_name)

    return ChainExecutionResponse(
        steps=list(context.steps),
        outputs=final_outputs,
        inputs=final_variables,
        final_output_key=final_output_key,
        final_output=final_output,
        model_provider=context.provider,
        provider=context.provider.value,
        model=context.model_spec.model_name,
        patient_context=context.patient_context,
        metadata=metadata,
    )


async def _build_execution_context(
    payload: ChainExecutionRequest,
    prompt_client: PromptCatalogClient,
    patient_client: PatientContextClient,
    settings: Settings,
) -> _ChainExecutionContext:
    model_identifier = payload.model.strip() if payload.model else None

    provider_hint = payload.model_provider
    if payload.provider:
        legacy_identifier = payload.provider.strip()
        if legacy_identifier:
            provider_hint = resolve_provider(legacy_identifier)

    variables: dict[str, Any] = {
        str(key): value for key, value in payload.variables.items()
    }
    available_variables = set(variables.keys())
    if payload.patient_id:
        variables.setdefault("patient_id", payload.patient_id)
        available_variables.add("patient_id")
    patient_context: EHRPatientContext | None = None
    request_categories = _filter_valid_categories(payload.categories or [])

    resolved_prompts_raw: list[ChatPrompt] = []
    prompt_from_catalog: list[bool] = []

    for index, item in enumerate(payload.chain):
        try:
            prompt = await _resolve_prompt(item, prompt_client)
        except PromptNotFoundError as exc:
            prompt_id = getattr(exc, "identifier", getattr(item, "value", str(item)))
            raise PromptNotFoundError(
                prompt_id,
                detail=str(exc),
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            ) from exc
        except PromptCatalogServiceError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
            ) from exc

        resolved_prompts_raw.append(prompt)
        prompt_from_catalog.append(isinstance(item, ChatPromptKey))

    if not resolved_prompts_raw:
        raise HTTPException(  # pragma: no cover - defensive
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Prompt chain cannot be empty.",
        )

    final_prompt = resolved_prompts_raw[-1]
    final_from_catalog = prompt_from_catalog[-1]
    prompt_model_identifier, prompt_provider_hint = _extract_prompt_model_preferences(
        final_prompt
    )

    if not model_identifier and prompt_model_identifier:
        model_identifier = prompt_model_identifier

    if prompt_provider_hint is not None:
        provider_hint = prompt_provider_hint

    needs_model_classifier = not model_identifier and (
        not final_from_catalog
        or (prompt_model_identifier is None and prompt_provider_hint is None)
    )

    if needs_model_classifier:
        slug = await _classify_model_slug(final_prompt, settings)
        if slug:
            model_identifier = slug
            try:
                provider_hint = resolve_provider(slug)
            except Exception:  # pragma: no cover - defensive logging
                logger.warning("prompt_model_classifier_invalid_slug", slug=slug)

    model_spec = resolve_model_spec(model_identifier, provider_hint=provider_hint)
    provider = model_spec.provider

    try:
        llm = provider.create_client(
            settings=settings,
            temperature=payload.temperature,
            model_override=model_identifier,
        )
    except (ProblemDetailsException, HTTPException):
        raise
    except Exception as exc:  # pragma: no cover - unexpected provider failure
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize language model: {exc}",
        ) from exc

    _apply_model_overrides(llm, max_tokens=payload.max_tokens, top_p=payload.top_p)

    category_classifier: CategoryClassifier | None = None
    prompt_categories: list[str] = []
    if final_from_catalog:
        prompt_categories = _filter_valid_categories(
            _get_prompt_categories(final_prompt)
        )

    final_categories: list[str] = []
    if prompt_categories:
        final_categories = prompt_categories
        _set_prompt_categories(final_prompt, final_categories)
    elif request_categories:
        final_categories = request_categories
        _set_prompt_categories(final_prompt, final_categories)
    else:
        category_classifier = await _ensure_prompt_categories(
            final_prompt, llm, category_classifier
        )
        final_categories = _filter_valid_categories(
            _get_prompt_categories(final_prompt)
        )

    if payload.patient_id:
        try:
            patient_context = await patient_client.get_patient_context(
                payload.patient_id,
                categories=final_categories or None,
            )
        except PatientNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        except PatientContextServiceError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
            ) from exc

    if patient_context is not None:
        context_dict = patient_context.model_dump(by_alias=True, exclude_none=True)
        variables.setdefault("patient_context", context_dict)

        json_ready_context = patient_context.model_dump(
            mode="json", by_alias=True, exclude_none=True
        )
        variables.setdefault(
            "patient_context_json",
            json.dumps(json_ready_context, ensure_ascii=False, indent=2),
        )
        available_variables.update({"patient_context", "patient_context_json"})

    derived_context = build_context_variables(patient_context)
    for key, value in derived_context.items():
        variables.setdefault(key, value)
    available_variables.update(derived_context.keys())

    used_output_keys: set[str] = set()
    resolved_prompts: list[_ResolvedPrompt] = []
    steps: list[ChainStepResult] = []

    for index, prompt in enumerate(resolved_prompts_raw):
        category_classifier = await _ensure_prompt_categories(
            prompt, llm, category_classifier
        )

        resolved = _prepare_prompt(prompt, index, available_variables, used_output_keys)
        resolved_prompts.append(resolved)
        steps.append(
            ChainStepResult(prompt=resolved.prompt, output_key=resolved.output_key)
        )
        available_variables.add(resolved.output_key)

    return _ChainExecutionContext(
        payload=payload,
        llm=llm,
        model_spec=model_spec,
        provider=provider,
        patient_context=patient_context,
        variables=variables,
        steps=steps,
        resolved_prompts=resolved_prompts,
    )


async def _execute_chain_buffered(
    context: _ChainExecutionContext,
) -> ChainExecutionResponse:
    variables = dict(context.variables)
    outputs: dict[str, Any] = {}

    for resolved in context.resolved_prompts:
        chain = _create_llm_chain(resolved, context.llm)
        result = await _invoke_llm_chain(chain, variables)
        normalized = _normalize_outputs(result)
        variables.update(normalized)
        outputs.update(normalized)

    return _finalize_response(context, variables=variables, outputs=outputs)


async def _iter_llm_stream(
    chain: LLMChain, variables: Mapping[str, Any]
) -> AsyncIterator[str]:
    astream_events = getattr(chain, "astream_events", None)
    if not callable(astream_events):
        return

    async for event in astream_events(variables, version="v1"):
        if not isinstance(event, Mapping):
            continue
        if event.get("event") != "on_llm_stream":
            continue
        data = event.get("data") or {}
        chunk = data.get("chunk")
        text = _coalesce_text(chunk)
        if text:
            yield text


async def _execute_chain_streaming(
    context: _ChainExecutionContext,
) -> AsyncIterator[str]:
    async def iterator() -> AsyncIterator[str]:
        variables = dict(context.variables)
        outputs: dict[str, Any] = {}

        final_resolved = (
            context.resolved_prompts[-1] if context.resolved_prompts else None
        )
        final_chain = (
            _create_llm_chain(final_resolved, context.llm)
            if final_resolved is not None
            else None
        )
        supports_streaming = bool(
            final_chain and callable(getattr(final_chain, "astream_events", None))
        )

        metadata_event = {
            "type": "metadata",
            "service": SERVICE_NAME,
            "provider": context.provider.value,
            "model": context.model_spec.model_name,
            "streaming": supports_streaming,
            "finalOutputKey": final_resolved.output_key if final_resolved else None,
            "patientId": context.payload.patient_id,
        }
        yield _format_sse_event(metadata_event)

        try:
            for resolved in context.resolved_prompts[:-1]:
                chain = _create_llm_chain(resolved, context.llm)
                result = await _invoke_llm_chain(chain, variables)
                normalized = _normalize_outputs(result)
                variables.update(normalized)
                outputs.update(normalized)

                step_output = normalized.get(resolved.output_key)
                if step_output is not None:
                    yield _format_sse_event(
                        {
                            "type": "step",
                            "outputKey": resolved.output_key,
                            "text": str(step_output),
                        }
                    )

            final_chunks: list[str] = []
            if final_resolved is not None and final_chain is not None:
                streaming_successful = False
                if supports_streaming:
                    try:
                        async for text_chunk in _iter_llm_stream(
                            final_chain, variables
                        ):
                            streaming_successful = True
                            final_chunks.append(text_chunk)
                            yield _format_sse_event(
                                {
                                    "type": "chunk",
                                    "outputKey": final_resolved.output_key,
                                    "text": text_chunk,
                                }
                            )
                    except Exception as exc:  # pragma: no cover - defensive logging
                        supports_streaming = False
                        logger.warning(
                            "llm_streaming_not_supported",
                            provider=context.provider.value,
                            error=str(exc),
                        )
                        yield _format_sse_event(
                            {
                                "type": "info",
                                "streaming": False,
                                "message": (
                                    "Streaming is not supported by the selected model. "
                                    "Falling back to a buffered response."
                                ),
                            }
                        )

                if not supports_streaming or not streaming_successful:
                    result = await _invoke_llm_chain(final_chain, variables)
                    normalized = _normalize_outputs(result)
                    variables.update(normalized)
                    outputs.update(normalized)
                    buffered_text = normalized.get(final_resolved.output_key)
                    if buffered_text is not None:
                        text_value = str(buffered_text)
                        final_chunks = [text_value]
                        yield _format_sse_event(
                            {
                                "type": "chunk",
                                "outputKey": final_resolved.output_key,
                                "text": text_value,
                                "buffered": True,
                            }
                        )

                supports_streaming = supports_streaming and streaming_successful
                final_text = "".join(final_chunks)
                outputs[final_resolved.output_key] = final_text
                variables[final_resolved.output_key] = final_text

            response = _finalize_response(context, variables=variables, outputs=outputs)
            yield _format_sse_event(
                {
                    "type": "response",
                    "streaming": supports_streaming,
                    "response": response.model_dump(
                        mode="json", by_alias=True, exclude_none=True
                    ),
                }
            )
        except ProblemDetailsException as exc:
            problem = exc.to_problem_details()
            yield _format_sse_event(
                {
                    "type": "error",
                    "status": problem.status,
                    "detail": problem.detail,
                    "title": problem.title,
                    "problem": problem.model_dump(mode="json", exclude_none=True),
                }
            )
        except HTTPException as exc:
            yield _format_sse_event(
                {
                    "type": "error",
                    "status": exc.status_code,
                    "detail": exc.detail,
                }
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("streaming_chain_execution_failed", error=str(exc))
            yield _format_sse_event(
                {
                    "type": "error",
                    "status": status.HTTP_502_BAD_GATEWAY,
                    "detail": f"Chain execution failed: {exc}",
                }
            )

    return iterator()


@router.post(
    "/execute",
    response_model=ChainExecutionResponse,
    status_code=status.HTTP_200_OK,
)
async def execute_chain(
    payload: ChainExecutionRequest,
    prompt_client: PromptCatalogClient = Depends(get_prompt_catalog_client),
    patient_client: PatientContextClient = Depends(get_patient_context_client),
    settings: Settings = Depends(get_settings),
) -> ChainExecutionResponse:
    """Execute a sequence of prompts using the configured language model provider."""

    context = await _build_execution_context(
        payload, prompt_client, patient_client, settings
    )
    return await _execute_chain_buffered(context)


@router.post(
    "/execute/stream",
    status_code=status.HTTP_200_OK,
)
async def stream_chain_execution(
    payload: ChainExecutionRequest,
    prompt_client: PromptCatalogClient = Depends(get_prompt_catalog_client),
    patient_client: PatientContextClient = Depends(get_patient_context_client),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    """Stream partial chain results as server-sent events."""

    context = await _build_execution_context(
        payload, prompt_client, patient_client, settings
    )
    iterator = await _execute_chain_streaming(context)
    headers = {"Cache-Control": "no-cache"}
    return StreamingResponse(iterator, media_type="text/event-stream", headers=headers)


app.include_router(router)


def get_app() -> FastAPI:
    """Return the configured FastAPI application."""

    return app


__all__ = ["app", "get_app", "health", "execute_chain", "stream_chain_execution"]
