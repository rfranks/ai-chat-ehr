"""Utilities and helpers for working with language-model providers."""

from .providers import LLMProvider
from .llmmodels import (
    DEFAULT_CANONICAL_MODEL_NAME,
    DEFAULT_PROVIDER,
    ModelSpec,
    available_model_specs,
    canonical_model_name,
    get_model_spec,
    resolve_model_name,
    resolve_model_spec,
    resolve_provider,
)
from .prompt_builder import (
    InvalidPromptTemplateError,
    MissingPromptTemplateError,
    PromptBuilderError,
    PromptTemplateSpec,
    PromptVariableMismatchError,
    build_context_variables,
    build_prompt_template,
)

__all__ = [
    "LLMProvider",
    "ModelSpec",
    "DEFAULT_PROVIDER",
    "DEFAULT_CANONICAL_MODEL_NAME",
    "available_model_specs",
    "canonical_model_name",
    "get_model_spec",
    "resolve_model_name",
    "resolve_model_spec",
    "resolve_provider",
    "PromptBuilderError",
    "MissingPromptTemplateError",
    "InvalidPromptTemplateError",
    "PromptVariableMismatchError",
    "PromptTemplateSpec",
    "build_prompt_template",
    "build_context_variables",
]
