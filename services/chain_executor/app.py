"""FastAPI application orchestrating prompt chain execution."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Mapping, Sequence

import httpx
from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from langchain.chains import LLMChain, SequentialChain
from langchain.prompts import PromptTemplate
from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.config.settings import Settings, get_settings
from shared.llm import resolve_model_spec, resolve_provider
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

SERVICE_NAME = "chain_executor"

app = FastAPI(title="Chain Executor Service")
router = APIRouter(prefix="/chains", tags=["chains"])


class ChainExecutorSettings(BaseSettings):
    """Configuration for interacting with upstream services."""

    prompt_catalog_url: AnyHttpUrl = Field(
        default="http://localhost:8001",
        description="Base URL for the prompt catalog service",
    )
    patient_context_url: AnyHttpUrl = Field(
        default="http://localhost:8002",
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
        _prompt_http_client = _create_http_client(str(settings.prompt_catalog_url), settings.http_timeout)
    return _prompt_http_client


async def get_patient_http_client(
    settings: ChainExecutorSettings = Depends(get_service_settings),
) -> httpx.AsyncClient:
    """Return a shared HTTP client for the patient context service."""

    global _context_http_client
    if _context_http_client is None:
        _context_http_client = _create_http_client(str(settings.patient_context_url), settings.http_timeout)
    return _context_http_client


class PromptCatalogServiceError(RuntimeError):
    """Raised when the prompt catalog service cannot satisfy a request."""


class PromptNotFoundError(PromptCatalogServiceError):
    """Raised when a prompt identifier cannot be resolved."""

    def __init__(self, identifier: str) -> None:
        super().__init__(f"Prompt '{identifier}' was not found.")
        self.identifier = identifier


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

    async def get_patient_context(self, patient_id: str) -> EHRPatientContext:
        normalized = patient_id.strip()
        if not normalized:
            raise PatientContextServiceError("Patient identifier cannot be empty")

        try:
            response = await self._http.get(
                "/patients/context", params={"patient_id": normalized}
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
    template_text = (prompt.template or "").strip()
    if not template_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Prompt '{_describe_prompt(prompt)}' does not define template text.",
        )

    try:
        template = PromptTemplate.from_template(template_text)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Prompt '{_describe_prompt(prompt)}' contains an invalid template: {exc}"
            ),
        ) from exc

    declared_variables = set(prompt.input_variables or [])
    derived_variables = set(template.input_variables)
    missing_declared = declared_variables - derived_variables
    if missing_declared:
        missing = ", ".join(sorted(missing_declared))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Prompt '{_describe_prompt(prompt)}' declares input variable(s) {missing} "
                "that are not present in the template."
            ),
        )

    input_variables = sorted(derived_variables)
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
        template=template,
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

    model_identifier = payload.model.strip() if payload.model else None

    provider_hint = payload.model_provider
    if payload.provider:
        legacy_identifier = payload.provider.strip()
        if legacy_identifier:
            provider_hint = resolve_provider(legacy_identifier)

    model_spec = resolve_model_spec(model_identifier, provider_hint=provider_hint)
    provider = model_spec.provider

    try:
        llm = provider.create_client(
            settings=settings,
            temperature=payload.temperature,
            model_override=model_identifier,
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - unexpected provider failure
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize language model: {exc}",
        ) from exc

    _apply_model_overrides(
        llm, max_tokens=payload.max_tokens, top_p=payload.top_p
    )

    patient_context: EHRPatientContext | None = None
    if payload.patient_id:
        try:
            patient_context = await patient_client.get_patient_context(payload.patient_id)
        except PatientNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        except PatientContextServiceError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
            ) from exc

    variables: dict[str, Any] = {
        str(key): value for key, value in payload.variables.items()
    }
    available_variables = set(variables.keys())
    if payload.patient_id:
        variables.setdefault("patient_id", payload.patient_id)
        available_variables.add("patient_id")
    if patient_context is not None:
        context_dict = patient_context.model_dump(by_alias=True, exclude_none=True)
        variables.setdefault("patient_context", context_dict)
        variables.setdefault(
            "patient_context_json",
            json.dumps(context_dict, ensure_ascii=False, indent=2),
        )
        available_variables.update({"patient_context", "patient_context_json"})

    used_output_keys: set[str] = set()
    resolved_prompts: list[_ResolvedPrompt] = []
    steps: list[ChainStepResult] = []

    for index, item in enumerate(payload.chain):
        try:
            prompt = await _resolve_prompt(item, prompt_client)
        except PromptNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
            ) from exc
        except PromptCatalogServiceError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
            ) from exc

        resolved = _prepare_prompt(prompt, index, available_variables, used_output_keys)
        resolved_prompts.append(resolved)
        steps.append(ChainStepResult(prompt=resolved.prompt, output_key=resolved.output_key))
        available_variables.add(resolved.output_key)

    llm_chains: list[LLMChain] = []
    output_keys: list[str] = []
    for resolved in resolved_prompts:
        chain = LLMChain(
            llm=llm,
            prompt=resolved.template,
            output_key=resolved.output_key,
        )
        llm_chains.append(chain)
        output_keys.append(resolved.output_key)

    sequential_chain = SequentialChain(
        chains=llm_chains,
        input_variables=sorted(variables.keys()),
        output_variables=output_keys,
        verbose=False,
    )

    try:
        if hasattr(sequential_chain, "ainvoke"):
            outputs = await sequential_chain.ainvoke(variables)
        else:  # pragma: no cover - fallback for legacy chain APIs
            outputs = await asyncio.to_thread(sequential_chain.invoke, variables)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - propagation of provider errors
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Chain execution failed: {exc}",
        ) from exc

    normalized_outputs = _normalize_outputs(outputs)
    final_output_key = output_keys[-1] if output_keys else None
    final_output = normalized_outputs.get(final_output_key) if final_output_key else None

    metadata = dict(payload.metadata)
    metadata.setdefault("service", SERVICE_NAME)
    metadata.setdefault("canonical_model", model_spec.canonical_name)

    return ChainExecutionResponse(
        steps=steps,
        outputs=normalized_outputs,
        inputs=variables,
        final_output_key=final_output_key,
        final_output=final_output,
        model_provider=provider,
        provider=provider.value,
        model=model_spec.model_name,
        patient_context=patient_context,
        metadata=metadata,
    )


app.include_router(router)


def get_app() -> FastAPI:
    """Return the configured FastAPI application."""

    return app


__all__ = ["app", "get_app", "health", "execute_chain"]
