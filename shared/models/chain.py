"""Data models describing prompt chain execution payloads."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Optional

from pydantic import Field, field_validator

from shared.llm import LLMProvider

from .chat import (
    CamelModel,
    ChatPrompt,
    ChatPromptKey,
    EHRPatientContext,
    PromptChainItem,
    _match_prompt_key,
)

# ---------------------------------------------------------------------------
# Public type aliases
# ---------------------------------------------------------------------------

PromptSelector = PromptChainItem


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------


class ChainStepResult(CamelModel):
    """Metadata describing a single executed step in a prompt chain."""

    prompt: ChatPrompt = Field(description="Resolved prompt configuration for the step")
    output_key: str = Field(description="Key assigned to the step's output")


class ChainExecutionRequest(CamelModel):
    """Request payload describing a prompt chain to execute."""

    chain: list[PromptSelector] = Field(
        description="Ordered prompts or raw instructions to execute",
        min_length=1,
    )
    patient_id: Optional[str] = Field(
        default=None, description="Optional patient identifier for context retrieval"
    )
    variables: dict[str, Any] = Field(
        default_factory=dict,
        description="Initial variables supplied to the chain for template rendering",
    )
    provider: Optional[str] = Field(
        default=None,
        description="Optional legacy provider identifier; prefer 'model_provider'",
    )
    model_provider: LLMProvider = Field(
        default=LLMProvider.OPENAI_GPT_35_TURBO,
        description="Language model provider to use for execution",
    )
    model: Optional[str] = Field(
        default=None, description="Optional model name override for the selected provider"
    )
    temperature: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Optional temperature override for generation",
    )
    max_tokens: Optional[int] = Field(
        default=None,
        ge=1,
        description="Optional maximum number of tokens for the final response",
    )
    top_p: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional nucleus sampling parameter",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary metadata for client bookkeeping"
    )

    @field_validator("chain", mode="before")
    @classmethod
    def _validate_chain(
        cls, value: Any
    ) -> Sequence[PromptSelector]:  # pragma: no cover - simple normalization
        return _normalize_prompt_selectors(value)


class ChainExecutionResponse(CamelModel):
    """Response payload returned after executing a prompt chain."""

    steps: list[ChainStepResult] = Field(
        default_factory=list,
        description="Resolved steps that were executed as part of the chain",
    )
    outputs: dict[str, Any] = Field(
        default_factory=dict,
        description="Mapping of step output keys to generated text",
    )
    inputs: dict[str, Any] = Field(
        default_factory=dict,
        description="Initial variables supplied for the execution",
    )
    final_output_key: Optional[str] = Field(
        default=None, description="Identifier for the final step in the chain"
    )
    final_output: Optional[Any] = Field(
        default=None, description="Content produced by the final step"
    )
    model_provider: Optional[LLMProvider] = Field(
        default=None,
        description="Canonical provider selected for execution",
    )
    provider: Optional[str] = Field(
        default=None,
        description="String representation of the provider used (deprecated)",
    )
    model: Optional[str] = Field(
        default=None,
        description="Provider specific model name used for execution",
    )
    patient_context: Optional[EHRPatientContext] = Field(
        default=None, description="Patient context payload retrieved for execution"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary metadata associated with the run"
    )

    @field_validator("steps", mode="before")
    @classmethod
    def _validate_steps(
        cls, value: Any
    ) -> Sequence[ChainStepResult]:  # pragma: no cover - simple normalization
        if value is None:
            return []
        if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, str)):
            return [ChainStepResult.model_validate(item) for item in value]
        raise TypeError("steps must be a sequence of ChainStepResult definitions")


# ---------------------------------------------------------------------------
# Shared normalization helpers
# ---------------------------------------------------------------------------


def _normalize_prompt_selectors(value: Any) -> list[PromptSelector]:
    """Normalize ``value`` into a list of prompt enums, models, or raw text."""

    if value is None:
        return []
    if isinstance(value, (ChatPromptKey, ChatPrompt, str)):
        value = [value]
    if isinstance(value, Mapping):
        value = [value]

    if not isinstance(value, Iterable) or isinstance(value, (bytes, bytearray, str)):
        raise TypeError("Chain must be a sequence of prompt identifiers or strings")

    normalized: list[PromptSelector] = []
    for item in value:
        normalized.append(_normalize_prompt_selector(item))

    return normalized


def _normalize_prompt_selector(item: Any) -> PromptSelector:
    """Normalize a single prompt selector entry."""

    if isinstance(item, ChatPrompt):
        return item
    if isinstance(item, ChatPromptKey):
        return item
    if isinstance(item, str):
        candidate = _match_prompt_key(item)
        if candidate is not None:
            return candidate
        stripped = item.strip()
        if not stripped:
            raise ValueError("Prompt selector entries cannot be empty strings")
        return stripped
    if isinstance(item, Mapping):
        prompt_enum = _extract_mapping_value(
            item, ["promptEnum", "prompt_enum", "promptKey", "prompt_key"]
        )
        if prompt_enum is not None:
            return _coerce_prompt_enum(prompt_enum)

        prompt_text = _extract_mapping_value(
            item,
            ["promptText", "prompt_text", "prompt", "text", "value", "raw"]
        )
        if prompt_text is not None:
            return _coerce_prompt_text(prompt_text)

        return ChatPrompt.model_validate(item)

    raise TypeError(
        "Unsupported prompt selector entry; expected ChatPromptKey, ChatPrompt, mapping, or string"
    )


def _extract_mapping_value(mapping: Mapping[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        if key in mapping:
            candidate = mapping[key]
            if candidate is None:
                continue
            if isinstance(candidate, str) and not candidate.strip():
                continue
            return candidate
    return None


def _coerce_prompt_enum(value: Any) -> ChatPromptKey:
    if isinstance(value, ChatPromptKey):
        return value
    if isinstance(value, str):
        candidate = _match_prompt_key(value)
        if candidate is not None:
            return candidate
        raise ValueError(f"Unknown prompt enum '{value}'")
    raise TypeError("promptEnum must be a string or ChatPromptKey value")


def _coerce_prompt_text(value: Any) -> str:
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise ValueError("Prompt text entries cannot be empty")
        return stripped
    raise TypeError("Prompt text must be provided as a string value")


__all__ = [
    "ChainExecutionRequest",
    "ChainExecutionResponse",
    "ChainStepResult",
    "PromptSelector",
]
