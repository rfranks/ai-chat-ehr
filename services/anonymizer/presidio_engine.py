"""Presidio-powered anonymization engine for Safe Harbor de-identification."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import hmac
import re
from typing import Callable, Iterable, Mapping, MutableSequence

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerResult


class AnonymizationAction(str, Enum):
    """Enumeration of supported anonymization strategies."""

    REDACT = "redact"
    REPLACE = "replace"
    SYNTHESIZE = "synthesize"


# Safe Harbor identifiers that should be anonymized.
# These entity names align with Presidio's default recognizers. Additional
# recognizers defined in :func:`_build_default_analyzer` extend coverage for
# insurance identifiers and facility names commonly found in telehealth data.
SAFE_HARBOR_ENTITIES: frozenset[str] = frozenset(
    {
        "PERSON",
        "PHONE_NUMBER",
        "EMAIL_ADDRESS",
        "US_SSN",
        "DATE_TIME",
        "LOCATION",
        "IP_ADDRESS",
        "URL",
        "MEDICAL_LICENSE",
        "HEALTH_INSURANCE_ID",
        "US_BANK_NUMBER",
        "US_DRIVER_LICENSE",
        "US_PASSPORT",
        "CREDIT_CARD",
        "CRYPTO",
        "AGE",
        "ORGANIZATION",
        "FACILITY_NAME",
        "ACCOUNT_NUMBER",
        "VIN",
        "IBAN_CODE",
    }
)


DEFAULT_REDACTION_TOKEN = "[REDACTED]"


@dataclass(slots=True)
class EntityAnonymizationRule:
    """Configuration describing how to anonymize a specific entity type."""

    action: AnonymizationAction
    replacement: str | None = None


@dataclass(slots=True)
class PresidioEngineConfig:
    """User configurable settings for :class:`PresidioAnonymizerEngine`."""

    default_action: AnonymizationAction = AnonymizationAction.REPLACE
    entity_policies: Mapping[str, EntityAnonymizationRule] = field(
        default_factory=dict
    )
    hash_secret: str = "ai-chat-ehr-safe-harbor"
    hash_prefix: str = "anon"
    hash_length: int = 12
    llm_model: str = "gpt-3.5-turbo-instruct"
    context_window: int = 50


def _build_default_analyzer() -> AnalyzerEngine:
    """Return an analyzer engine enriched with healthcare recognizers."""

    analyzer = AnalyzerEngine()

    registry = analyzer.registry

    # Recognize health insurance identifiers (alphanumeric policy numbers) and
    # facility names (e.g., nursing homes or telehealth facilities) which are
    # frequently mentioned in transcripts.
    registry.add_recognizer(
        PatternRecognizer(
            supported_entity="HEALTH_INSURANCE_ID",
            name="health_insurance_policy",
            context=["insurance", "policy", "payer"],
            patterns=[
                Pattern(
                    name="insurance-id",
                    regex=r"\b[A-Z]{2}[0-9A-Z]{6,12}\b",
                    score=0.35,
                )
            ],
        )
    )

    registry.add_recognizer(
        PatternRecognizer(
            supported_entity="FACILITY_NAME",
            name="facility_name",
            context=["facility", "hospital", "clinic", "center", "home"],
            patterns=[
                Pattern(
                    name="facility",
                    regex=r"\b[A-Z][A-Za-z]+(?:\s[A-Z][A-Za-z]+){0,3}\s(?:Center|Clinic|Hospital|Home|Facility)\b",
                    score=0.30,
                )
            ],
        )
    )

    # Recognize account-like identifiers that are frequently considered PHI
    # (medical record numbers, member IDs, etc.).
    registry.add_recognizer(
        PatternRecognizer(
            supported_entity="ACCOUNT_NUMBER",
            name="account_identifier",
            patterns=[
                Pattern(
                    name="account-id",
                    regex=r"\b\d{6,12}\b",
                    score=0.30,
                )
            ],
            context=["account", "medical", "record", "member", "mrn"],
        )
    )

    # Recognize numeric ages over 89 to convert them to the Safe Harbor bucket.
    registry.add_recognizer(
        PatternRecognizer(
            supported_entity="AGE",
            name="age_over_89",
            patterns=[
                Pattern(
                    name="age-words",
                    regex=r"\b(9[0-9]|[1-9][0-9]{2,})(?=\s*(?:years?\s*old|yo|y/o|yrs?))",
                    score=0.45,
                ),
                Pattern(
                    name="age-numeric",
                    regex=r"\b(9[0-9]|[1-9][0-9]{2,})\b",
                    score=0.40,
                ),
            ],
            context=["age"],
        )
    )

    return analyzer


class OpenAILLMSynthesizer:
    """Generate synthetic surrogates via the OpenAI API."""

    def __init__(
        self,
        model: str = "gpt-3.5-turbo-instruct",
        temperature: float = 0.6,
        max_tokens: int = 20,
    ) -> None:
        try:
            from openai import OpenAI
        except Exception as exc:  # pragma: no cover - defensive import guard
            raise RuntimeError(
                "OpenAI client is required for LLM-based synthesis but is not available"
            ) from exc

        self._client = OpenAI()
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    def __call__(
        self, entity_type: str, original: str, context: str | None = None
    ) -> str:
        prompt = (
            "You are assisting with HIPAA Safe Harbor anonymization. "
            "Generate a realistic but fictitious surrogate for the detected "
            f"{entity_type.replace('_', ' ').lower()} given the original value. "
            "Do not reuse the original text, but retain domain relevance. "
            "Respond with a single concise surrogate only."
        )
        if context:
            prompt += f"\nContext: {context.strip()}"
        prompt += f"\nOriginal: {original}\nSurrogate:"

        response = self._client.responses.create(
            model=self._model,
            input=prompt,
            temperature=self._temperature,
            max_output_tokens=self._max_tokens,
        )

        # ``output_text`` is available on Responses API results. Fallback to the
        # first candidate if the helper attribute is missing for compatibility
        # with older client versions.
        surrogate = getattr(response, "output_text", None)
        if surrogate:
            return surrogate.strip()

        try:  # pragma: no cover - compatibility fallback
            return response.output[0].content[0].text.strip()  # type: ignore[index, attr-defined]
        except Exception:  # pragma: no cover - compatibility fallback
            choice = getattr(response, "choices", [{}])[0]
            message = getattr(choice, "message", None)
            if isinstance(message, dict):
                content = message.get("content", "")
            else:
                content = getattr(message, "content", "")
            return str(content).strip()


class PresidioAnonymizerEngine:
    """Anonymize PHI leveraging Microsoft Presidio and configurable strategies."""

    def __init__(
        self,
        *,
        analyzer: AnalyzerEngine | None = None,
        config: PresidioEngineConfig | None = None,
        synthesizer: Callable[[str, str, str | None], str] | None = None,
    ) -> None:
        self._config = config or PresidioEngineConfig()
        self._analyzer = analyzer or _build_default_analyzer()
        self._synthesizer = synthesizer
        if self._config.default_action is AnonymizationAction.SYNTHESIZE and not synthesizer:
            self._synthesizer = OpenAILLMSynthesizer(model=self._config.llm_model)

    def anonymize(self, text: str, *, language: str = "en") -> str:
        """Apply Safe Harbor anonymization policies to ``text``."""

        results = self._analyzer.analyze(text=text, language=language)
        replacements: MutableSequence[tuple[int, int, str]] = []

        occupied: list[tuple[int, int]] = []
        for result in sorted(results, key=lambda r: (r.start, -r.end)):
            if not self._should_anonymize(result):
                continue
            if self._overlaps(result, occupied):
                continue

            original_value = text[result.start : result.end]
            action = self._resolve_action(result.entity_type)

            if action is AnonymizationAction.REDACT:
                replacement = self._resolve_redaction_token(result)
            elif action is AnonymizationAction.REPLACE:
                replacement = self._hash_value(result.entity_type, original_value)
            elif action is AnonymizationAction.SYNTHESIZE:
                replacement = self._synthesize_value(text, result, original_value)
            else:  # pragma: no cover - exhaustiveness guard
                raise ValueError(f"Unsupported anonymization action: {action}")

            replacements.append((result.start, result.end, replacement))
            occupied.append((result.start, result.end))

        anonymized_text = text
        for start, end, replacement in sorted(replacements, key=lambda r: r[0], reverse=True):
            anonymized_text = anonymized_text[:start] + replacement + anonymized_text[end:]

        anonymized_text = self._generalize_ages(anonymized_text)
        return anonymized_text

    def _should_anonymize(self, result: RecognizerResult) -> bool:
        return result.entity_type in SAFE_HARBOR_ENTITIES

    def _resolve_action(self, entity_type: str) -> AnonymizationAction:
        policy = self._config.entity_policies.get(entity_type)
        if policy:
            return policy.action
        return self._config.default_action

    def _resolve_redaction_token(self, result: RecognizerResult) -> str:
        policy = self._config.entity_policies.get(result.entity_type)
        if policy and policy.replacement:
            return policy.replacement
        return DEFAULT_REDACTION_TOKEN

    def _hash_value(self, entity_type: str, value: str) -> str:
        digest = hmac.new(
            key=self._config.hash_secret.encode("utf-8"),
            msg=f"{entity_type}:{value}".encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()
        prefix = self._config.hash_prefix
        length = self._config.hash_length
        if length:
            digest = digest[:length]
        return f"{prefix}_{digest}"

    def _synthesize_value(
        self, text: str, result: RecognizerResult, original_value: str
    ) -> str:
        if not self._synthesizer:
            self._synthesizer = OpenAILLMSynthesizer(model=self._config.llm_model)

        window = self._config.context_window
        start_context = max(result.start - window, 0)
        end_context = min(result.end + window, len(text))
        context = text[start_context:result.start] + text[result.end:end_context]

        return self._synthesizer(result.entity_type, original_value, context or None)

    @staticmethod
    def _overlaps(result: RecognizerResult, occupied: Iterable[tuple[int, int]]) -> bool:
        for start, end in occupied:
            if result.start < end and start < result.end:
                return True
        return False

    @staticmethod
    def _generalize_ages(text: str) -> str:
        def repl(match: re.Match[str]) -> str:
            return match.group(0).replace(match.group(1), "90+")

        patterns = [
            re.compile(
                r"\b((?:9[0-9]|[1-9][0-9]{2,}))\b(?=\s*(?:years?\s*old|yo|y/o|yrs?))",
                flags=re.IGNORECASE,
            ),
            re.compile(
                r"\bage\s*(?:is|was|:)?\s*(9[0-9]|[1-9][0-9]{2,})",
                flags=re.IGNORECASE,
            ),
        ]

        for pattern in patterns:
            text = pattern.sub(repl, text)

        return text


__all__ = [
    "AnonymizationAction",
    "EntityAnonymizationRule",
    "OpenAILLMSynthesizer",
    "PresidioAnonymizerEngine",
    "PresidioEngineConfig",
    "SAFE_HARBOR_ENTITIES",
]

