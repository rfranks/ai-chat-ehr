"""Common chat-oriented data models for ChatEHR services."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date, datetime
from enum import Enum
from typing import Any, Mapping, Optional, Sequence, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def to_camel(value: str) -> str:
    """Convert ``snake_case`` ``value`` into ``camelCase`` for JSON aliases."""

    components = value.split("_")
    if not components:
        return value
    first, *rest = components
    return first + "".join(token.capitalize() for token in rest)


SNAKE_CASE_BOUNDARY = re.compile(r"(?<!^)(?=[A-Z])")


def _to_snake_case(text: str) -> str:
    """Return a normalized snake_case representation of ``text``."""

    cleaned = text.strip()
    if not cleaned:
        return ""
    cleaned = (
        cleaned.replace("-", " ").replace("/", " ").replace(":", " ").replace(".", " ")
    )
    tokens: list[str] = []
    for token in cleaned.split():
        if not token:
            continue
        tokens.append(SNAKE_CASE_BOUNDARY.sub("_", token).lower())
    return "_".join(tokens)


# ---------------------------------------------------------------------------
# Chat prompt definitions
# ---------------------------------------------------------------------------


class ChatPromptKey(str, Enum):
    """Canonical identifiers for reusable chat prompts."""

    PATIENT_CONTEXT = "patient_context"
    PATIENT_SUMMARY = "patient_summary"
    DIFFERENTIAL_DIAGNOSIS = "differential_diagnosis"
    CLINICAL_PLAN = "clinical_plan"
    FOLLOW_UP_QUESTIONS = "follow_up_questions"
    PATIENT_EDUCATION = "patient_education"
    SAFETY_CHECKS = "safety_checks"
    TRIAGE_ASSESSMENT = "triage_assessment"

    def __str__(self) -> str:  # pragma: no cover - trivial wrapper
        return self.value


PromptChainItem = Union["ChatPromptKey", "ChatPrompt", str]


def _match_prompt_key(text: str) -> Optional[ChatPromptKey]:
    """Return the :class:`ChatPromptKey` matching ``text`` if possible."""

    normalized = _to_snake_case(text)
    if not normalized:
        return None
    for member in ChatPromptKey:
        if normalized == _to_snake_case(member.value):
            return member
        if normalized == _to_snake_case(member.name):
            return member
    return None


class CamelModel(BaseModel):
    """Base model applying camelCase aliases and ignoring unknown fields."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )


class ChatPrompt(CamelModel):
    """Metadata describing a reusable chat prompt template."""

    key: Optional[ChatPromptKey] = Field(
        default=None, description="Canonical identifier for the prompt"
    )
    title: Optional[str] = Field(default=None, description="Human readable label")
    description: Optional[str] = Field(
        default=None, description="Detailed explanation of the prompt's purpose"
    )
    categories: Optional[list[str]] = Field(
        default_factory=list,
        description="The categories of data rquired to answer or fullfil the prompt",
    )
    template: Optional[str] = Field(
        default=None,
        description="Prompt template text that may contain replacement variables",
    )
    input_variables: list[str] = Field(
        default_factory=list,
        description="Names of variables expected by the template",
    )
    chain: list[PromptChainItem] = Field(
        default_factory=list,
        description=(
            "Sequence of additional prompts or raw instructions to execute prior to "
            "this prompt"
        ),
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary metadata for the prompt"
    )
    model: Optional[str] = Field(
        default=None, description="The model best suited to answer this prompt"
    )

    @field_validator("chain", mode="before")
    @classmethod
    def _validate_chain(
        cls, value: Any
    ) -> Sequence[PromptChainItem]:  # pragma: no cover - simple normalization
        return _normalize_chain(value)

    @model_validator(mode="after")
    def _ensure_content(self) -> "ChatPrompt":
        if not (self.template or self.chain):
            raise ValueError(
                "ChatPrompt requires either a template or a non-empty chain of prompts"
            )
        return self


# ---------------------------------------------------------------------------
# Patient record definitions
# ---------------------------------------------------------------------------


class PatientDemographics(CamelModel):
    """Structured demographic attributes about a patient."""

    patient_id: Optional[str] = Field(default=None, description="Unique patient id")
    mrn: Optional[str] = Field(default=None, description="Medical record number")
    first_name: Optional[str] = Field(default=None)
    middle_name: Optional[str] = Field(default=None)
    last_name: Optional[str] = Field(default=None)
    full_name: Optional[str] = Field(default=None)
    prefix: Optional[str] = Field(default=None)
    suffix: Optional[str] = Field(default=None)
    date_of_birth: Optional[date] = Field(default=None)
    age: Optional[int] = Field(default=None)
    gender: Optional[str] = Field(default=None)
    biological_sex: Optional[str] = Field(default=None)
    pronouns: Optional[str] = Field(default=None)
    race: Optional[str] = Field(default=None)
    ethnicity: Optional[str] = Field(default=None)
    marital_status: Optional[str] = Field(default=None)
    language: Optional[str] = Field(default=None)
    occupation: Optional[str] = Field(default=None)
    address: Optional[str] = Field(default=None)
    phone: Optional[str] = Field(default=None)
    email: Optional[str] = Field(default=None)
    preferred_contact_method: Optional[str] = Field(default=None)


class Encounter(CamelModel):
    """Basic information about a clinical encounter."""

    encounter_id: Optional[str] = Field(default=None)
    type: Optional[str] = Field(default=None)
    reason: Optional[str] = Field(default=None)
    start: Optional[datetime] = Field(default=None)
    end: Optional[datetime] = Field(default=None)
    location: Optional[str] = Field(default=None)
    provider: Optional[str] = Field(default=None)
    status: Optional[str] = Field(default=None)
    notes: Optional[str] = Field(default=None)


class Medication(CamelModel):
    """Medication order or administration details."""

    name: Optional[str] = Field(default=None)
    dose: Optional[str] = Field(default=None)
    route: Optional[str] = Field(default=None)
    frequency: Optional[str] = Field(default=None)
    start_date: Optional[datetime] = Field(default=None)
    end_date: Optional[datetime] = Field(default=None)
    as_needed: Optional[bool] = Field(default=None)
    indication: Optional[str] = Field(default=None)
    status: Optional[str] = Field(default=None)
    instructions: Optional[str] = Field(default=None)


class Allergy(CamelModel):
    """Allergy or intolerance record."""

    substance: Optional[str] = Field(default=None)
    reaction: Optional[str] = Field(default=None)
    severity: Optional[str] = Field(default=None)
    status: Optional[str] = Field(default=None)
    noted_date: Optional[datetime] = Field(default=None)
    comments: Optional[str] = Field(default=None)


class Procedure(CamelModel):
    """Procedures performed or planned for the patient."""

    name: Optional[str] = Field(default=None)
    date: Optional[datetime] = Field(default=None)
    status: Optional[str] = Field(default=None)
    performer: Optional[str] = Field(default=None)
    notes: Optional[str] = Field(default=None)


class ImagingStudy(CamelModel):
    """Summary details from imaging studies."""

    modality: Optional[str] = Field(default=None)
    study: Optional[str] = Field(default=None)
    performed_at: Optional[datetime] = Field(default=None)
    findings: Optional[str] = Field(default=None)
    impression: Optional[str] = Field(default=None)


class Immunization(CamelModel):
    """Immunization history details."""

    vaccine: Optional[str] = Field(default=None)
    date: Optional[datetime] = Field(default=None)
    lot_number: Optional[str] = Field(default=None)
    status: Optional[str] = Field(default=None)
    notes: Optional[str] = Field(default=None)


class LabResult(CamelModel):
    """Laboratory result details."""

    test_code: Optional[str] = Field(default=None)
    test_name: Optional[str] = Field(default=None)
    value: Optional[str] = Field(default=None)
    unit: Optional[str] = Field(default=None)
    reference_range: Optional[str] = Field(default=None)
    abnormal_flag: Optional[str] = Field(default=None)
    status: Optional[str] = Field(default=None)
    collected_at: Optional[datetime] = Field(default=None)
    resulted_at: Optional[datetime] = Field(default=None)
    notes: Optional[str] = Field(default=None)


class VitalSign(CamelModel):
    """Individual vital sign measurement."""

    type: Optional[str] = Field(default=None)
    value: Optional[str] = Field(default=None)
    unit: Optional[str] = Field(default=None)
    taken_at: Optional[datetime] = Field(default=None)
    qualifier: Optional[str] = Field(default=None)


class Problem(CamelModel):
    """Problem list entry."""

    name: Optional[str] = Field(default=None)
    status: Optional[str] = Field(default=None)
    onset: Optional[datetime] = Field(default=None)
    resolved: Optional[datetime] = Field(default=None)
    notes: Optional[str] = Field(default=None)


class ClinicalNote(CamelModel):
    """Clinical note metadata and content."""

    note_id: Optional[str] = Field(default=None)
    title: Optional[str] = Field(default=None)
    note_type: Optional[str] = Field(default=None)
    created_at: Optional[datetime] = Field(default=None)
    author: Optional[str] = Field(default=None)
    content: Optional[str] = Field(default=None)


class ClinicalDocument(CamelModel):
    """Structured clinical documents linked to the record."""

    document_id: Optional[str] = Field(default=None)
    title: Optional[str] = Field(default=None)
    category: Optional[str] = Field(default=None)
    created_at: Optional[datetime] = Field(default=None)
    author: Optional[str] = Field(default=None)
    content: Optional[str] = Field(default=None)
    url: Optional[str] = Field(default=None)


class CareTeamMember(CamelModel):
    """Care team participants."""

    name: Optional[str] = Field(default=None)
    role: Optional[str] = Field(default=None)
    organization: Optional[str] = Field(default=None)
    contact: Optional[str] = Field(default=None)


class SocialHistoryItem(CamelModel):
    """Social history elements relevant to the encounter."""

    category: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    recorded_at: Optional[datetime] = Field(default=None)


class FamilyHistoryItem(CamelModel):
    """Family history item."""

    relationship: Optional[str] = Field(default=None)
    condition: Optional[str] = Field(default=None)
    status: Optional[str] = Field(default=None)
    notes: Optional[str] = Field(default=None)


class CarePlanItem(CamelModel):
    """Entries in a care plan or set of recommendations."""

    title: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    status: Optional[str] = Field(default=None)
    due: Optional[datetime] = Field(default=None)


class PatientRecord(CamelModel):
    """Aggregate structure capturing the patient's longitudinal record."""

    demographics: Optional[PatientDemographics] = Field(default=None)
    encounters: list[Encounter] = Field(default_factory=list)
    medications: list[Medication] = Field(default_factory=list)
    allergies: list[Allergy] = Field(default_factory=list)
    procedures: list[Procedure] = Field(default_factory=list)
    imaging: list[ImagingStudy] = Field(default_factory=list)
    immunizations: list[Immunization] = Field(default_factory=list)
    lab_results: list[LabResult] = Field(default_factory=list)
    vital_signs: list[VitalSign] = Field(default_factory=list)
    problems: list[Problem] = Field(default_factory=list)
    clinical_notes: list[ClinicalNote] = Field(default_factory=list)
    clinical_documents: list[ClinicalDocument] = Field(default_factory=list)
    care_team: list[CareTeamMember] = Field(default_factory=list)
    social_history: list[SocialHistoryItem] = Field(default_factory=list)
    family_history: list[FamilyHistoryItem] = Field(default_factory=list)


class EHRPatientContext(PatientRecord):
    """Patient context payload curated for chat workflows."""

    chief_complaint: Optional[str] = Field(default=None)
    history_of_present_illness: Optional[str] = Field(default=None)
    assessment: Optional[str] = Field(default=None)
    plan: Optional[str] = Field(default=None)
    goals: list[CarePlanItem] = Field(default_factory=list)
    follow_up_actions: list[str] = Field(default_factory=list)
    additional_notes: list[ClinicalNote] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Chat orchestration models
# ---------------------------------------------------------------------------


class ChatMessageRole(str, Enum):
    """Roles used in chat transcripts."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ChatMessage(CamelModel):
    """Message exchanged during a chat conversation."""

    role: ChatMessageRole = Field(description="Sender role for the message")
    content: str = Field(description="Message content")
    name: Optional[str] = Field(default=None, description="Optional participant name")
    created_at: Optional[datetime] = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatQuestion(CamelModel):
    """High-level question posed by a clinician or operator."""

    question: str = Field(description="Natural language question to answer")
    id: Optional[str] = Field(default=None, description="Client supplied identifier")
    chain: list[PromptChainItem] = Field(
        default_factory=list,
        description="Ordered prompts or text snippets to run before answering",
    )
    messages: list[ChatMessage] = Field(
        default_factory=list, description="Prior conversation messages"
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("chain", mode="before")
    @classmethod
    def _validate_chain(
        cls, value: Any
    ) -> Sequence[PromptChainItem]:  # pragma: no cover - simple normalization
        return _normalize_chain(value)


class ChatRequest(CamelModel):
    """Envelope for executing chat-based clinical workflows."""

    question: ChatQuestion = Field(description="Question to route through prompts")
    patient_context: Optional[EHRPatientContext] = Field(
        default=None, description="Structured patient information"
    )
    chain: list[PromptChainItem] = Field(
        default_factory=list,
        description="Overrides or additional prompts for the request",
    )
    model: Optional[str] = Field(default=None, description="Model identifier override")
    provider: Optional[str] = Field(default=None, description="LLM provider override")
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("chain", mode="before")
    @classmethod
    def _validate_chain(
        cls, value: Any
    ) -> Sequence[PromptChainItem]:  # pragma: no cover - simple normalization
        return _normalize_chain(value)

    @model_validator(mode="after")
    def _merge_question_chain(self) -> "ChatRequest":
        if not self.chain and self.question.chain:
            self.chain = list(self.question.chain)
        return self


class ChatResponse(CamelModel):
    """Standardized chat response payload."""

    answer: str = Field(description="LLM generated answer")
    question: Optional[ChatQuestion] = Field(default=None)
    chain: list[PromptChainItem] = Field(
        default_factory=list,
        description="Chain of prompts applied during generation",
    )
    messages: list[ChatMessage] = Field(
        default_factory=list, description="Messages exchanged to produce the answer"
    )
    usage: Optional[dict[str, Any]] = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("chain", mode="before")
    @classmethod
    def _validate_chain(
        cls, value: Any
    ) -> Sequence[PromptChainItem]:  # pragma: no cover - simple normalization
        return _normalize_chain(value)


# ---------------------------------------------------------------------------
# Shared chain normalization logic
# ---------------------------------------------------------------------------


def _normalize_chain(value: Any) -> list[PromptChainItem]:
    """Normalize ``value`` into a list of prompt enums, models, or raw text."""

    if value is None:
        return []
    if isinstance(value, (ChatPromptKey, ChatPrompt, str)):
        value = [value]
    if isinstance(value, Mapping):
        value = [value]

    if not isinstance(value, Iterable) or isinstance(value, (bytes, bytearray, str)):
        raise TypeError("Chain must be a sequence of prompt identifiers or strings")

    normalized: list[PromptChainItem] = []
    for item in value:
        if isinstance(item, ChatPrompt):
            normalized.append(item)
            continue
        if isinstance(item, ChatPromptKey):
            normalized.append(item)
            continue
        if isinstance(item, Mapping):
            normalized.append(ChatPrompt.model_validate(item))
            continue
        if isinstance(item, str):
            candidate = _match_prompt_key(item)
            if candidate is not None:
                normalized.append(candidate)
            else:
                stripped = item.strip()
                if not stripped:
                    raise ValueError("Chain entries cannot be empty strings")
                normalized.append(stripped)
            continue
        raise TypeError(
            f"Unsupported chain entry of type {type(item)!r}; expected ChatPromptKey, "
            "ChatPrompt, mapping, or string"
        )

    return normalized


__all__ = [
    "Allergy",
    "CarePlanItem",
    "CareTeamMember",
    "ChatMessage",
    "ChatMessageRole",
    "ChatPrompt",
    "ChatPromptKey",
    "ChatQuestion",
    "ChatRequest",
    "ChatResponse",
    "ClinicalDocument",
    "ClinicalNote",
    "EHRPatientContext",
    "Encounter",
    "FamilyHistoryItem",
    "ImagingStudy",
    "Immunization",
    "LabResult",
    "Medication",
    "PatientDemographics",
    "PatientRecord",
    "Problem",
    "Procedure",
    "PromptChainItem",
    "SocialHistoryItem",
    "VitalSign",
]
