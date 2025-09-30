"""Repository abstractions for the prompt catalog service."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from shared.models.chat import ChatPrompt, ChatPromptKey, _match_prompt_key


class PromptRepository:
    """In-memory repository for managing :class:`ChatPrompt` definitions."""

    def __init__(self, prompts: Iterable[ChatPrompt] | None = None) -> None:
        self._prompts: dict[str, ChatPrompt] = {}
        if prompts is not None:
            for prompt in prompts:
                identifier = self._identifier_for_prompt(prompt)
                self._prompts[identifier] = prompt

    async def list_prompts(self) -> list[ChatPrompt]:
        """Return all known prompts ordered by insertion."""

        return list(self._prompts.values())

    async def get_prompt(self, prompt_id: str | ChatPromptKey) -> ChatPrompt | None:
        """Return a prompt matching ``prompt_id`` if one exists."""

        identifier = self._normalize_identifier(prompt_id)
        return self._prompts.get(identifier)

    async def search_prompts(
        self,
        *,
        query: str | None = None,
        key: ChatPromptKey | None = None,
        categories: Iterable[str] | None = None,
        limit: int = 20,
    ) -> list[ChatPrompt]:
        """Return prompts filtered by ``query`` and ``key``.

        Parameters
        ----------
        query:
            Optional text that should appear within the prompt metadata or template.
        key:
            Optional :class:`ChatPromptKey` to filter for an exact prompt identifier.
        categories:
            Optional collection of category slugs. Prompts must contain at least one of
            the provided slugs in their ``categories`` attribute or metadata
            ``categories`` entry.
        limit:
            Maximum number of results to return. A negative value is treated as zero.
        """

        normalized_key = self._normalize_identifier(key) if key else None
        normalized_query = query.lower().strip() if query else None
        normalized_categories = (
            {
                slug
                for slug in (
                    self._normalize_category_slug(value) for value in categories or []
                )
                if slug
            }
            if categories
            else None
        )

        if limit <= 0:
            return []

        results: list[ChatPrompt] = []
        for identifier, prompt in self._prompts.items():
            if normalized_key and identifier != normalized_key:
                continue

            if normalized_query and not self._matches_query(prompt, normalized_query):
                continue

            if normalized_categories and not self._matches_categories(
                prompt, normalized_categories
            ):
                continue

            results.append(prompt)
            if len(results) >= limit:
                break
        return results

    def _matches_query(self, prompt: ChatPrompt, query: str) -> bool:
        """Return ``True`` if ``query`` appears within prompt metadata."""

        parts: list[str] = []
        if isinstance(prompt.key, ChatPromptKey):
            parts.append(prompt.key.value)
        elif prompt.key:
            parts.append(str(prompt.key))
        if prompt.title:
            parts.append(prompt.title)
        if prompt.description:
            parts.append(prompt.description)
        if prompt.template:
            parts.append(prompt.template)
        if prompt.metadata:
            for value in prompt.metadata.values():
                if value is None:
                    continue
                if isinstance(value, str):
                    normalized = value
                else:
                    normalized = str(value)
                if normalized:
                    parts.append(normalized)
        haystack = " ".join(parts).lower()
        return query in haystack

    def _matches_categories(self, prompt: ChatPrompt, categories: set[str]) -> bool:
        """Return ``True`` when the prompt intersects ``categories``."""

        prompt_categories = self._extract_categories(prompt)
        if not prompt_categories:
            return False
        return not prompt_categories.isdisjoint(categories)

    def _extract_categories(self, prompt: ChatPrompt) -> set[str]:
        """Return the normalised category slugs for ``prompt``."""

        categories: set[str] = set()
        for value in prompt.categories or []:
            slug = self._normalize_category_slug(value)
            if slug:
                categories.add(slug)

        metadata = prompt.metadata or {}
        if metadata:
            raw_metadata_categories = metadata.get("categories")
            for value in self._iterate_category_values(raw_metadata_categories):
                slug = self._normalize_category_slug(value)
                if slug:
                    categories.add(slug)
        return categories

    def _iterate_category_values(self, value: Any) -> Iterable[str]:
        """Yield raw category values from ``value`` regardless of structure."""

        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, Mapping):
            return [str(value)]
        if isinstance(value, Iterable):
            results: list[str] = []
            for item in value:
                if isinstance(item, str):
                    results.append(item)
                elif item is not None:
                    results.append(str(item))
            return results
        return [str(value)]

    @staticmethod
    def _normalize_category_slug(value: Any) -> str:
        """Normalise a category value to a lowercase slug."""

        if value is None:
            return ""
        if not isinstance(value, str):
            value = str(value)
        stripped = value.strip()
        if not stripped:
            return ""
        return stripped.lower()

    def _identifier_for_prompt(self, prompt: ChatPrompt) -> str:
        """Return the canonical identifier for ``prompt`` for dictionary storage."""

        if prompt.key is not None:
            identifier = self._normalize_identifier(prompt.key)
            if identifier:
                return identifier

        if prompt.metadata and "id" in prompt.metadata:
            raw_identifier = prompt.metadata.get("id")
            if raw_identifier is not None:
                identifier = self._normalize_identifier(str(raw_identifier))
                if identifier:
                    return identifier

        if prompt.title:
            identifier = self._normalize_identifier(prompt.title)
            if identifier:
                return identifier
        raise ValueError(
            "Prompt requires either a key, metadata id, or title for identification"
        )

    @staticmethod
    def _normalize_identifier(value: str | ChatPromptKey) -> str:
        """Normalize the identifier for lookups."""

        if isinstance(value, ChatPromptKey):
            return value.value

        stripped = value.strip()
        if not stripped:
            return ""

        matched_key = _match_prompt_key(stripped)
        if matched_key is not None:
            return matched_key.value

        lowered = stripped.lower()
        enum_prefix = f"{ChatPromptKey.__name__.lower()}"
        for member in ChatPromptKey:
            member_name = member.name.lower()
            member_value = member.value.lower()
            if lowered in {member_name, member_value, f"{enum_prefix}.{member_name}"}:
                return member.value

        return lowered


# TODO: Replace the in-memory repository with a database-backed implementation when
# persistent storage is available for the prompt catalog service.
_DEFAULT_PROMPTS: tuple[ChatPrompt, ...] = (
    ChatPrompt(
        key=ChatPromptKey.PATIENT_CONTEXT,
        title="Patient Context Overview",
        description="Summarize clinical background and social determinants for the visit.",
        template=(
            "You are drafting a concise patient context summary using the provided "
            "clinical background: {patient_background}. Highlight key risk factors, "
            "recent events, and any notable social determinants of health."
        ),
        input_variables=["patient_background"],
        categories=["patientDetail", "problems", "socialHistory", "careTeam"],
    ),
    ChatPrompt(
        key=ChatPromptKey.CLINICAL_PLAN,
        title="Clinical Plan Outline",
        description="Construct a draft plan that covers assessment, diagnostics, and treatment.",
        template=(
            "Using the encounter data in {encounter_overview}, craft a step-by-step clinical "
            "plan addressing differential diagnoses, recommended studies, and follow-up."
        ),
        input_variables=["encounter_overview"],
        categories=["problems", "orders", "medications", "labs", "testResults"],
    ),
    ChatPrompt(
        key=ChatPromptKey.FOLLOW_UP_QUESTIONS,
        title="Follow-up Question Suggestions",
        description="Suggest clarifying questions to ask the patient during follow-up.",
        template=(
            "Given the patient summary {patient_summary}, generate targeted follow-up "
            "questions to explore unresolved issues and safety concerns."
        ),
        input_variables=["patient_summary"],
        categories=["notes", "problems", "patientDetail"],
    ),
    ChatPrompt(
        key=ChatPromptKey.PATIENT_SUMMARY,
        title="Comprehensive Patient Summary",
        description="Produce an integrated narrative that blends demographics, history, and active concerns.",
        template=(
            "Integrate the structured details below into a cohesive patient summary. "
            "Demographics: {demographics}. Active problems: {active_problems}. "
            "Recent clinical highlights: {clinical_highlights}. Focus on trends and "
            "clinical relevance for the current encounter."
        ),
        input_variables=["demographics", "active_problems", "clinical_highlights"],
        categories=["patientDetail", "problems", "notes"],
    ),
    ChatPrompt(
        key=ChatPromptKey.DIFFERENTIAL_DIAGNOSIS,
        title="Differential Diagnosis Explorer",
        description="Outline prioritized differential diagnoses with supporting evidence and next steps.",
        template=(
            "Given the chief concern {chief_complaint} and key findings {clinical_findings}, "
            "list the top differential diagnoses. For each, summarise supporting/contradicting "
            "data and note recommended diagnostics to confirm or exclude the condition."
        ),
        input_variables=["chief_complaint", "clinical_findings"],
        categories=["problems", "labs", "testResults", "notes"],
    ),
    ChatPrompt(
        key=ChatPromptKey.PATIENT_EDUCATION,
        title="Patient Education Brief",
        description="Draft plain-language counseling points tailored to the patient's condition and treatments.",
        template=(
            "Using the treatment plan {treatment_plan} and patient considerations {patient_considerations}, "
            "create education points that explain the condition, medications, lifestyle adjustments, "
            "and follow-up needs in accessible language. Highlight safety precautions and when to seek care."
        ),
        input_variables=["treatment_plan", "patient_considerations"],
        categories=["medications", "carePlans", "socialHistory"],
    ),
    ChatPrompt(
        key=ChatPromptKey.SAFETY_CHECKS,
        title="Care Safety Checklist",
        description="Review high-risk medications, allergies, and monitoring requirements for safety.",
        template=(
            "Review the active medication list {active_medications}, allergy history {allergy_history}, "
            "and recent vitals {recent_vitals}. Summarize potential safety concerns such as interactions, "
            "contraindications, or monitoring gaps, and recommend mitigation steps."
        ),
        input_variables=["active_medications", "allergy_history", "recent_vitals"],
        categories=["medications", "allergies", "vitals", "orders"],
    ),
    ChatPrompt(
        key=ChatPromptKey.TRIAGE_ASSESSMENT,
        title="Urgency Triage Assessment",
        description="Assess visit urgency based on presenting symptoms, vitals, and risk factors.",
        template=(
            "Given the presenting symptoms {presenting_symptoms}, vital trends {triage_vitals}, "
            "and notable risk factors {risk_factors}, determine the appropriate triage level. "
            "Justify the recommendation with specific findings and suggest immediate interventions if needed."
        ),
        input_variables=["presenting_symptoms", "triage_vitals", "risk_factors"],
        categories=["vitals", "patientDetail", "riskScores", "encounters"],
    ),
)

_PROMPT_REPOSITORY = PromptRepository(_DEFAULT_PROMPTS)


def get_prompt_repository() -> PromptRepository:
    """Dependency provider returning the application's prompt repository."""

    return _PROMPT_REPOSITORY
