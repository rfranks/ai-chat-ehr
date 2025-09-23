"""Chains that classify prompts into thematic categories."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

__all__ = [
    "PromptCategory",
    "DEFAULT_PROMPT_CATEGORIES",
    "CategoryClassifier",
]


@dataclass(frozen=True)
class PromptCategory:
    """Metadata describing a logical category for an EHR prompt."""

    slug: str
    name: str
    description: str
    aliases: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation of the category."""

        return {
            "slug": self.slug,
            "name": self.name,
            "description": self.description,
            "aliases": list(self.aliases),
        }


DEFAULT_PROMPT_CATEGORIES: tuple[PromptCategory, ...] = (
    PromptCategory(
        slug="patient_context",
        name="Patient Context",
        description="Summaries of the patient's clinical background, history, or context.",
        aliases=("context", "patient_background"),
    ),
    PromptCategory(
        slug="clinical_assessment",
        name="Clinical Assessment",
        description="Reasoning about diagnoses, differential diagnoses, or assessments.",
        aliases=("assessment", "differential", "diagnosis"),
    ),
    PromptCategory(
        slug="care_plan",
        name="Care Plan",
        description="Constructing treatment recommendations, management plans, or next steps.",
        aliases=("plan", "management_plan", "treatment_plan"),
    ),
    PromptCategory(
        slug="follow_up_questions",
        name="Follow-up Questions",
        description="Generating additional questions or clarifications for clinicians or patients.",
        aliases=("questions", "follow_up"),
    ),
    PromptCategory(
        slug="patient_education",
        name="Patient Education",
        description="Explaining conditions, plans, or instructions in patient-friendly language.",
        aliases=("education", "patient_guidance"),
    ),
    PromptCategory(
        slug="safety",
        name="Safety Checks",
        description="Identifying red flags, safety issues, or risk mitigations.",
        aliases=("safety_checks", "risk"),
    ),
    PromptCategory(
        slug="triage",
        name="Triage",
        description="Assessing acuity or determining the urgency of clinical scenarios.",
        aliases=("triage_assessment", "triage_check"),
    ),
    PromptCategory(
        slug="general_reasoning",
        name="General Reasoning",
        description="Prompts that span multiple workflows or do not neatly fit other categories.",
        aliases=("general", "misc", "other"),
    ),
)

_CLASSIFIER_TEMPLATE = """
You are an expert curator for an electronic health record (EHR) prompt library.

Select every category slug from the allowed list that applies to the prompt.
Use only the slugs listed below and respond with a JSON array of slugs. If none apply,
respond with an empty array ``[]``. Do not invent new categories.

Allowed categories (slug – name – description):
{category_overview}

Structured category metadata:
{category_json}

Prompt metadata (JSON):
{prompt_json}
""".strip()

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.IGNORECASE | re.DOTALL)
_JSON_ARRAY_RE = re.compile(r"\[[^\]]*\]", re.DOTALL)
_JSON_OBJECT_RE = re.compile(r"\{[^\}]*\}", re.DOTALL)


def _normalize_token(value: str) -> str:
    token = re.sub(r"[^0-9a-zA-Z]+", "_", value.strip().lower())
    return token.strip("_")


def _deduplicate_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _build_alias_map(categories: Sequence[PromptCategory]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for category in categories:
        for candidate in (category.slug, category.name, *category.aliases):
            normalized = _normalize_token(candidate)
            if not normalized:
                continue
            mapping[normalized] = category.slug
    return mapping


def _render_category_overview(categories: Sequence[PromptCategory]) -> str:
    lines: list[str] = []
    for category in categories:
        alias_text = ""
        if category.aliases:
            alias_text = f" (aliases: {', '.join(category.aliases)})"
        lines.append(
            f"- {category.slug} – {category.name}{alias_text}: {category.description}"
        )
    return "\n".join(lines)


def _render_category_json(categories: Sequence[PromptCategory]) -> str:
    payload = [category.as_dict() for category in categories]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _strip_code_fence(text: str) -> str:
    match = _CODE_FENCE_RE.match(text.strip())
    if match:
        return match.group(1).strip()
    return text.strip()


def _candidate_json_fragments(text: str) -> list[str]:
    stripped = _strip_code_fence(text)
    if not stripped:
        return []
    candidates = [stripped]
    candidates.extend(match.group(0) for match in _JSON_ARRAY_RE.finditer(stripped))
    candidates.extend(match.group(0) for match in _JSON_OBJECT_RE.finditer(stripped))
    return _deduplicate_preserve_order(candidates)


def _iter_possible_values(payload: Any) -> Iterable[str]:
    if payload is None:
        return []
    if isinstance(payload, str):
        return [payload]
    if isinstance(payload, Mapping):
        explicit = payload.get("slug") or payload.get("id") or payload.get("name")
        if isinstance(explicit, str):
            return [explicit]
        for key in ("categories", "labels", "values", "tags"):
            if key in payload:
                return _iter_possible_values(payload[key])
        return []
    if isinstance(payload, Iterable):
        results: list[str] = []
        for item in payload:
            results.extend(_iter_possible_values(item))
        return results
    return [str(payload)]


class CategoryClassifier:
    """Wrapper around a :class:`LLMChain` for prompt categorisation."""

    def __init__(self, chain: LLMChain, categories: Sequence[PromptCategory]) -> None:
        self._chain = chain
        self._categories = tuple(categories)
        self._alias_map = _build_alias_map(self._categories)

    @classmethod
    def create(
        cls, llm: Any, categories: Sequence[PromptCategory] | None = None
    ) -> "CategoryClassifier":
        """Create a classifier bound to ``llm`` and the provided ``categories``."""

        selected = tuple(categories or DEFAULT_PROMPT_CATEGORIES)
        prompt = PromptTemplate.from_template(_CLASSIFIER_TEMPLATE).partial(
            category_overview=_render_category_overview(selected),
            category_json=_render_category_json(selected),
        )
        chain = LLMChain(llm=llm, prompt=prompt, output_key="categories")
        return cls(chain, selected)

    @property
    def chain(self) -> LLMChain:
        """Return the underlying :class:`LLMChain`."""

        return self._chain

    @property
    def categories(self) -> tuple[PromptCategory, ...]:
        """Return the known categories used by the classifier."""

        return self._categories

    def parse_response(self, text: str) -> list[str]:
        """Parse ``text`` into a list of canonical category slugs."""

        stripped = text.strip()
        if not stripped:
            return []

        for candidate in _candidate_json_fragments(stripped):
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            resolved = self._extract_slugs(payload)
            if resolved:
                return resolved

        return self._parse_fallback(stripped)

    def _extract_slugs(self, payload: Any) -> list[str]:
        values = _iter_possible_values(payload)
        resolved: list[str] = []
        for value in values:
            slug = self._resolve_slug(value)
            if slug:
                resolved.append(slug)
        return _deduplicate_preserve_order(resolved)

    def _parse_fallback(self, text: str) -> list[str]:
        tokens = re.split(r"[,\n]+", text)
        resolved: list[str] = []
        for token in tokens:
            slug = self._resolve_slug(token)
            if slug:
                resolved.append(slug)
        return _deduplicate_preserve_order(resolved)

    def _resolve_slug(self, value: str) -> str | None:
        normalized = _normalize_token(value)
        if not normalized:
            return None
        return self._alias_map.get(normalized)
