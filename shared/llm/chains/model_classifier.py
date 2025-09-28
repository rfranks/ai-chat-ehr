"""Chains that classify prompts to select an appropriate LLM model."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

from shared.llm.llmmodels import DEFAULT_MODEL_PROVIDER

__all__ = [
    "LLMModelClassifierMetadata",
    "DEFAULT_MODEL_CLASSIFIER_MODELS",
    "ModelClassifier",
]


@dataclass(frozen=True)
class LLMModelClassifierMetadata:
    """Structured metadata describing an LLM option for model routing."""

    vendor: str
    model: str
    provider: str
    description: str
    aliases: tuple[str, ...] = ()
    strengths: tuple[str, ...] = ()
    weaknesses: tuple[str, ...] = ()
    supported_modalities: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation of the model metadata."""

        return {
            "vendor": self.vendor,
            "model": self.model,
            "provider": self.provider,
            "description": self.description,
            "aliases": list(self.aliases),
            "strengths": list(self.strengths),
            "weaknesses": list(self.weaknesses),
            "supportedModalities": list(self.supported_modalities),
        }


DEFAULT_MODEL_CLASSIFIER_MODELS: tuple[LLMModelClassifierMetadata, ...] = (
    LLMModelClassifierMetadata(
        vendor="OpenAI",
        model="GPT-4o",
        provider="openai/gpt-4o",
        description=(
            "Flagship OpenAI multimodal model offering strong reasoning for "
            "clinical summarisation, code synthesis, and mixed modality inputs."
        ),
        aliases=("gpt-4o", "o4", "openai-gpt-4o"),
        strengths=(
            "High-quality reasoning across structured and unstructured data",
            "Handles mixed text and image context when available",
            "Strong guardrails for safety-critical conversations",
        ),
        weaknesses=(
            "Higher cost and latency than lighter models",
            "May over-refuse niche clinical edge cases",
        ),
        supported_modalities=("text", "images"),
    ),
    LLMModelClassifierMetadata(
        vendor="OpenAI",
        model="GPT-4o mini",
        provider="openai/gpt-4o-mini",
        description=(
            "Smaller OpenAI multimodal model optimised for rapid responses and "
            "tool use with moderate reasoning strength."
        ),
        aliases=("gpt-4o-mini", "o4-mini", "openai-gpt-4o-mini"),
        strengths=(
            "Fast responses suitable for interactive chart review",
            "Good balance of quality and cost for general tasks",
            "Supports tool outputs and lightweight multimodal prompts",
        ),
        weaknesses=(
            "Less reliable on long-form clinical planning",
            "Struggles with extensive code generation compared to larger models",
        ),
        supported_modalities=("text", "images"),
    ),
    LLMModelClassifierMetadata(
        vendor="OpenAI",
        model="GPT-3.5 Turbo",
        provider="openai/gpt-3.5-turbo",
        description=(
            "Efficient chat model suited for lightweight instructions, templated "
            "messages, and deterministic transformations."
        ),
        aliases=(
            "gpt-3.5-turbo",
            "gpt-3.5",
            "gpt35",
            "openai-gpt-3.5",
            "chatgpt",
        ),
        strengths=(
            "Low latency for simple summarisation or extraction",
            "Cost-effective for high-volume automation",
            "Deterministic style when paired with low temperature",
        ),
        weaknesses=(
            "Limited complex reasoning ability",
            "No native multimodal understanding",
        ),
        supported_modalities=("text",),
    ),
    LLMModelClassifierMetadata(
        vendor="Azure OpenAI",
        model="GPT-4o",
        provider="azure/gpt-4o",
        description=(
            "Azure-hosted GPT-4o variant with enterprise controls and regional "
            "deployment flexibility."
        ),
        aliases=("azure-gpt-4o", "microsoft-azure-gpt-4o"),
        strengths=(
            "Enterprise compliance and private networking support",
            "Consistent behaviour with public GPT-4o",
            "Supports Azure-managed authentication and quotas",
        ),
        weaknesses=(
            "Requires Azure deployment configuration",
            "Availability varies by region",
        ),
        supported_modalities=("text", "images"),
    ),
    LLMModelClassifierMetadata(
        vendor="Azure OpenAI",
        model="GPT-4o mini",
        provider="azure/gpt-4o-mini",
        description=(
            "Azure-hosted lightweight GPT-4o variant ideal for rapid feedback "
            "with enterprise guarantees."
        ),
        aliases=("azure-gpt-4o-mini", "azure-mini"),
        strengths=(
            "Fast responses for iterative workflows",
            "Enterprise telemetry and policy controls",
            "Lower operational cost compared to full GPT-4o",
        ),
        weaknesses=(
            "Reduced reasoning depth on complex analytics",
            "Requires Azure-specific deployment management",
        ),
        supported_modalities=("text", "images"),
    ),
    LLMModelClassifierMetadata(
        vendor="Anthropic",
        model="Claude 3 Sonnet",
        provider="anthropic/claude-3-sonnet",
        description=(
            "Balanced Claude model delivering strong reasoning, long context, and "
            "measured safety alignment."
        ),
        aliases=("claude-3-sonnet", "claude-sonnet", "sonnet"),
        strengths=(
            "Excellent long-form clinical narrative synthesis",
            "Strong constitutional guardrails for sensitive content",
            "Good coding and structured reasoning capabilities",
        ),
        weaknesses=(
            "Higher latency versus Haiku or GPT-4o mini",
            "Limited multimodal support (text only)",
        ),
        supported_modalities=("text",),
    ),
    LLMModelClassifierMetadata(
        vendor="Anthropic",
        model="Claude 3 Haiku",
        provider="anthropic/claude-3-haiku",
        description=(
            "Fastest Claude 3 family member optimised for lightweight reasoning and "
            "classification tasks."
        ),
        aliases=("claude-3-haiku", "claude-haiku", "haiku"),
        strengths=(
            "Very low latency for triage-style prompts",
            "Robust refusal behaviour for unsafe instructions",
            "Cost efficient for batch automation",
        ),
        weaknesses=(
            "Weaker performance on complex reasoning",
            "Text-only model without image support",
        ),
        supported_modalities=("text",),
    ),
    LLMModelClassifierMetadata(
        vendor="Google",
        model="Gemini 2.5 Pro",
        provider="vertex/gemini-2.5-pro",
        description=(
            "Google Vertex AI hosted Gemini model for multimodal clinical workflows "
            "requiring image or file reasoning."
        ),
        aliases=("gemini-2.5-pro", "gemini-pro", "google-gemini-pro"),
        strengths=(
            "Strong multimodal understanding including imaging studies",
            "Tight integration with Google Cloud tooling",
            "Large context window for longitudinal records",
        ),
        weaknesses=(
            "Requires Vertex AI project configuration",
            "Response style may need additional grounding",
        ),
        supported_modalities=("text", "images", "files"),
    ),
    LLMModelClassifierMetadata(
        vendor="Google",
        model="Gemini 2.5 Flash",
        provider="vertex/gemini-2.5-flash",
        description=(
            "Lower latency Gemini model suitable for UI co-pilots and quick "
            "summaries with basic multimodal ability."
        ),
        aliases=("gemini-2.5-flash", "gemini-flash", "google-gemini-flash"),
        strengths=(
            "Responsive experience for clinician-facing assistants",
            "Optimised for tool calling and structured outputs",
            "Supports text and lightweight image inputs",
        ),
        weaknesses=(
            "Reduced depth for nuanced clinical reasoning",
            "Needs careful prompting for extended narratives",
        ),
        supported_modalities=("text", "images"),
    ),
)


_MODEL_TEMPLATE = "{provider} – {vendor} {model} – {description}"


def _render_model_overview(models: Sequence[LLMModelClassifierMetadata]) -> str:
    lines: list[str] = []
    for model in models:
        lines.append(
            _MODEL_TEMPLATE.format(
                provider=model.provider,
                vendor=model.vendor,
                model=model.model,
                description=model.description.strip().replace("\n", " "),
            )
        )
    return "\n".join(lines)


def _render_model_json(models: Sequence[LLMModelClassifierMetadata]) -> str:
    payload = [model.as_dict() for model in models]
    return json.dumps(payload, ensure_ascii=False, indent=2)


_CLASSIFIER_TEMPLATE = """
You are an expert curator for selecting language models for an electronic health record (EHR) assistant.

Choose the single best model provider slug from the allowed list that can satisfy the prompt safely and effectively.
Respond with a JSON object of the form {"model": "<provider slug>"} using only the allowed provider slugs.

Allowed models (provider – vendor/model – description):
{model_overview}

Structured model metadata:
{model_json}

Prompt metadata (JSON):
{{prompt_json}}
""".strip()


_JSON_OBJECT_RE = re.compile(r"\{[^{}]*\}")
_CODE_FENCE_RE = re.compile(r"^```(?:json)?\n(?P<content>.*)```$", re.DOTALL)
_TOKEN_SANITIZER = re.compile(r"[^a-z0-9]+")


def _normalize_alias(text: str) -> str:
    cleaned = _TOKEN_SANITIZER.sub("", text.strip().lower())
    return cleaned


def _deduplicate_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _build_alias_map(models: Sequence[LLMModelClassifierMetadata]) -> dict[str, str]:
    alias_map: dict[str, str] = {}
    for model in models:
        canonical = model.provider.strip()
        aliases = set(
            _deduplicate_preserve_order(
                (
                    canonical,
                    canonical.replace("/", "-"),
                    canonical.replace("/", ":"),
                    model.model,
                    model.vendor,
                    f"{model.vendor} {model.model}",
                    *model.aliases,
                )
            )
        )
        for alias in aliases:
            normalized = _normalize_alias(alias)
            if not normalized or normalized in alias_map:
                continue
            alias_map[normalized] = canonical
    return alias_map


def _strip_code_fence(text: str) -> str:
    match = _CODE_FENCE_RE.match(text.strip())
    if match:
        return match.group("content").strip()
    return text.strip()


def _candidate_json_fragments(text: str) -> list[str]:
    stripped = _strip_code_fence(text)
    if not stripped:
        return []
    candidates = [stripped]
    candidates.extend(match.group(0) for match in _JSON_OBJECT_RE.finditer(stripped))
    return _deduplicate_preserve_order(candidates)


def _extract_candidate_strings(payload: Any) -> Iterable[str]:
    if payload is None:
        return []
    if isinstance(payload, str):
        return [payload]
    if isinstance(payload, Mapping):
        candidates: list[str] = []
        for key in ("model", "provider", "slug", "id", "value"):
            value = payload.get(key)
            if isinstance(value, str):
                candidates.append(value)
        return candidates
    if isinstance(payload, Iterable) and not isinstance(payload, (bytes, bytearray)):
        results: list[str] = []
        for item in payload:
            results.extend(_extract_candidate_strings(item))
        return results
    return [str(payload)]


class ModelClassifier:
    """Wrapper around an :class:`LLMChain` for model selection."""

    def __init__(
        self, chain: LLMChain, models: Sequence[LLMModelClassifierMetadata]
    ) -> None:
        self._chain = chain
        self._models = tuple(models)
        self._alias_map = _build_alias_map(self._models)

    @classmethod
    def create(
        cls, llm: Any, models: Sequence[LLMModelClassifierMetadata] | None = None
    ) -> "ModelClassifier":
        """Create a classifier bound to ``llm`` and the provided ``models``."""

        selected = tuple(models or DEFAULT_MODEL_CLASSIFIER_MODELS)
        prompt = PromptTemplate.from_template(_CLASSIFIER_TEMPLATE).partial(
            model_overview=_render_model_overview(selected),
            model_json=_render_model_json(selected),
        )
        chain = LLMChain(llm=llm, prompt=prompt, output_key="model")
        return cls(chain, selected)

    @property
    def chain(self) -> LLMChain:
        """Return the underlying :class:`LLMChain`."""

        return self._chain

    def parse_response(self, text: str) -> str | None:
        """Parse ``text`` into a canonical provider slug string."""

        stripped = text.strip()
        if not stripped:
            return None

        for candidate in _candidate_json_fragments(stripped):
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            resolved = self._extract_slug(payload)
            if resolved:
                return resolved

        normalized = _normalize_alias(stripped)
        if not normalized:
            return None
        return self._alias_map.get(normalized)

    def _extract_slug(self, payload: Any) -> str | None:
        for candidate in _extract_candidate_strings(payload):
            normalized = _normalize_alias(candidate)
            if not normalized:
                continue
            slug = self._alias_map.get(normalized)
            if slug:
                return slug
        return None


# Export DEFAULT_MODEL_PROVIDER for external modules relying on this namespace.
DEFAULT_MODEL_PROVIDER  # pragma: no cover - re-export sentinel usage
