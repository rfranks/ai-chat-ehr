"""Repository abstractions for the prompt catalog service."""

from __future__ import annotations

from collections.abc import Iterable

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
        limit: int = 20,
    ) -> list[ChatPrompt]:
        """Return prompts filtered by ``query`` and ``key``.

        Parameters
        ----------
        query:
            Optional text that should appear within the prompt metadata or template.
        key:
            Optional :class:`ChatPromptKey` to filter for an exact prompt identifier.
        limit:
            Maximum number of results to return. A negative value is treated as zero.
        """

        normalized_key = self._normalize_identifier(key) if key else None
        normalized_query = query.lower().strip() if query else None

        if limit <= 0:
            return []

        results: list[ChatPrompt] = []
        for identifier, prompt in self._prompts.items():
            if normalized_key and identifier != normalized_key:
                continue

            if normalized_query and not self._matches_query(prompt, normalized_query):
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
        haystack = " ".join(parts).lower()
        return query in haystack

    def _identifier_for_prompt(self, prompt: ChatPrompt) -> str:
        """Return the canonical identifier for ``prompt`` for dictionary storage."""

        if prompt.key is not None:
            return self._normalize_identifier(prompt.key)
        if prompt.metadata and "id" in prompt.metadata:
            return self._normalize_identifier(str(prompt.metadata["id"]))
        if prompt.title:
            return self._normalize_identifier(prompt.title)
        raise ValueError("Prompt requires either a key, metadata id, or title for identification")

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
    ),
)

_PROMPT_REPOSITORY = PromptRepository(_DEFAULT_PROMPTS)


def get_prompt_repository() -> PromptRepository:
    """Dependency provider returning the application's prompt repository."""

    return _PROMPT_REPOSITORY
