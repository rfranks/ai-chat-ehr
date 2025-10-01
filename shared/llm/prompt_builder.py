"""Utilities for constructing prompt templates and derived variables."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping, Sequence

from langchain.prompts import PromptTemplate

from shared.models.chat import (
    Allergy,
    CarePlanItem,
    ChatPrompt,
    EHRPatientContext,
    LabResult,
    Medication,
    Problem,
)

EHRPrompt = ChatPrompt


class PromptBuilderError(ValueError):
    """Base error raised when converting prompt definitions."""


class MissingPromptTemplateError(PromptBuilderError):
    """Raised when a prompt definition omits template text."""


class InvalidPromptTemplateError(PromptBuilderError):
    """Raised when the prompt template text cannot be parsed."""


class PromptVariableMismatchError(PromptBuilderError):
    """Raised when declared prompt variables do not appear in the template."""

    def __init__(self, missing_variables: Sequence[str]) -> None:
        missing = tuple(missing_variables)
        message = ", ".join(missing)
        super().__init__(
            message
            if message
            else "Prompt declares variables missing from the template"
        )
        self.missing_variables: tuple[str, ...] = missing


@dataclass(frozen=True)
class PromptTemplateSpec:
    """Materialized prompt template metadata."""

    template: PromptTemplate
    input_variables: tuple[str, ...]


def build_prompt_template(prompt: EHRPrompt) -> PromptTemplateSpec:
    """Return a :class:`PromptTemplate` for ``prompt``.

    Parameters
    ----------
    prompt:
        Prompt definition describing template text and declared variables.

    Raises
    ------
    MissingPromptTemplateError
        If the prompt does not include template text.
    InvalidPromptTemplateError
        If the template text is not valid for :class:`PromptTemplate`.
    PromptVariableMismatchError
        If declared ``input_variables`` do not appear within the template.
    """

    template_text = (prompt.template or "").strip()
    if not template_text:
        raise MissingPromptTemplateError("Prompt definition is missing template text")

    try:
        template = PromptTemplate.from_template(template_text)
    except ValueError as exc:  # pragma: no cover - defensive programming
        raise InvalidPromptTemplateError(str(exc)) from exc

    declared = tuple(prompt.input_variables or [])
    derived = tuple(dict.fromkeys(template.input_variables))

    missing_declared = set(declared) - set(derived)
    if missing_declared:
        raise PromptVariableMismatchError(sorted(missing_declared))

    return PromptTemplateSpec(template=template, input_variables=derived)


ContextTransformer = Callable[[EHRPatientContext | None], Any]


def build_context_variables(
    context: EHRPatientContext | None,
    *,
    transformers: Mapping[str, ContextTransformer] | None = None,
) -> dict[str, Any]:
    """Return derived variables produced from ``context``.

    ``transformers`` may be supplied to extend or override the default
    context-derived variable functions.
    """

    registry: dict[str, ContextTransformer] = dict(_CONTEXT_TRANSFORMERS)
    if transformers:
        registry.update(transformers)

    derived: dict[str, Any] = {}
    for name, transformer in registry.items():
        value = transformer(context)
        if value is None:
            continue
        derived[name] = value
    return derived


def _summarize_patient(context: EHRPatientContext | None) -> str:
    if context is None:
        return "Patient summary is not available."

    lines: list[str] = []

    demographics = context.demographics
    if demographics:
        identity_parts: list[str] = []
        if demographics.full_name:
            identity_parts.append(demographics.full_name)
        else:
            names = [
                demographics.first_name,
                demographics.middle_name,
                demographics.last_name,
            ]
            identity = " ".join(part for part in names if part)
            if identity:
                identity_parts.append(identity)

        descriptors: list[str] = []
        if demographics.age is not None:
            descriptors.append(f"{demographics.age} y/o")
        elif demographics.date_of_birth is not None:
            descriptors.append(f"DOB {demographics.date_of_birth.isoformat()}")
        if demographics.gender:
            descriptors.append(demographics.gender)
        if (
            demographics.biological_sex
            and demographics.biological_sex != demographics.gender
        ):
            descriptors.append(f"biological sex {demographics.biological_sex}")
        if demographics.pronouns:
            descriptors.append(f"pronouns {demographics.pronouns}")

        descriptor_text = ", ".join(descriptors)
        if identity_parts:
            header = identity_parts[0]
            if descriptor_text:
                header = f"{header} ({descriptor_text})"
            lines.append(header)
        elif descriptor_text:
            lines.append(descriptor_text)

    if context.chief_complaint:
        lines.append(f"Chief complaint: {context.chief_complaint}")
    if context.history_of_present_illness:
        lines.append(f"HPI: {context.history_of_present_illness}")
    if context.assessment:
        lines.append(f"Assessment: {context.assessment}")
    if context.plan:
        lines.append(f"Plan: {context.plan}")

    problem_entries = [
        description
        for problem in context.problems
        if (description := _describe_problem(problem))
    ]
    if problem_entries:
        lines.append("Active problems: " + "; ".join(problem_entries))

    medication_entries = [
        description
        for medication in context.medications
        if (description := _describe_medication(medication))
    ]
    if medication_entries:
        lines.append("Medications: " + "; ".join(medication_entries))

    allergy_entries = [
        description
        for allergy in context.allergies
        if (description := _describe_allergy(allergy))
    ]
    if allergy_entries:
        lines.append("Allergies: " + "; ".join(allergy_entries))

    goal_entries = [
        description for goal in context.goals if (description := _describe_goal(goal))
    ]
    if goal_entries:
        lines.append("Care goals: " + "; ".join(goal_entries))

    follow_ups = [item for item in context.follow_up_actions if item]
    if follow_ups:
        lines.append("Follow-up actions: " + "; ".join(follow_ups))

    return "\n".join(lines) if lines else "No patient summary available."


def _summarize_labs(context: EHRPatientContext | None) -> str:
    if context is None or not context.lab_results:
        return "No laboratory results available."

    lines: list[str] = []
    for lab in context.lab_results:
        entry = _describe_lab_result(lab)
        if entry:
            lines.append(entry)

    return "\n".join(lines) if lines else "No laboratory results available."


def _describe_problem(problem: Problem | None) -> str | None:
    if problem is None:
        return None
    if not problem.name:
        return None

    parts = [problem.name]
    qualifiers: list[str] = []
    if problem.status:
        qualifiers.append(problem.status)
    if problem.notes:
        qualifiers.append(problem.notes)
    if qualifiers:
        parts.append("(" + "; ".join(qualifiers) + ")")
    return " ".join(parts)


def _describe_medication(medication: Medication | None) -> str | None:
    if medication is None or not medication.name:
        return None

    details = [
        part
        for part in [medication.dose, medication.route, medication.frequency]
        if part
    ]
    text = medication.name
    if details:
        text += " – " + " ".join(details)
    if medication.instructions:
        if details:
            text += f" ({medication.instructions})"
        else:
            text += f" – {medication.instructions}"
    return text


def _describe_allergy(allergy: Allergy | None) -> str | None:
    if allergy is None or not allergy.substance:
        return None

    text = allergy.substance
    descriptors = [
        item for item in [allergy.reaction, allergy.severity, allergy.status] if item
    ]
    if descriptors:
        text += " (" + ", ".join(descriptors) + ")"
    return text


def _describe_goal(goal: CarePlanItem | None) -> str | None:
    if goal is None or not goal.title:
        return None
    if goal.description:
        return f"{goal.title} – {goal.description}"
    return goal.title


def _describe_lab_result(lab: LabResult | None) -> str | None:
    if lab is None:
        return None

    name = lab.test_name or lab.test_code
    if not name:
        name = "Lab result"

    measurement_parts = [lab.value or ""]
    if lab.unit:
        measurement_parts.append(lab.unit)
    measurement = " ".join(part for part in measurement_parts if part) or "n/a"

    detail = f"- {name}: {measurement}"

    annotations: list[str] = []
    if lab.abnormal_flag:
        annotations.append(f"flag {lab.abnormal_flag}")
    if lab.reference_range:
        annotations.append(f"ref {lab.reference_range}")
    if lab.status:
        annotations.append(f"status {lab.status}")
    timestamp = lab.resulted_at or lab.collected_at
    if timestamp:
        annotations.append(_format_timestamp(timestamp))
    if annotations:
        detail += " (" + ", ".join(annotations) + ")"
    if lab.notes:
        detail += f" – {lab.notes}"
    return detail


def _format_timestamp(value: datetime | None) -> str:
    if value is None:
        return ""
    try:
        return value.isoformat(timespec="minutes")
    except TypeError:  # pragma: no cover - fallback for Python <3.11 behavior
        return value.replace(microsecond=0).isoformat()


_CONTEXT_TRANSFORMERS: Mapping[str, ContextTransformer] = {
    "patient_summary": _summarize_patient,
    "labs": _summarize_labs,
}


__all__ = [
    "EHRPrompt",
    "PromptBuilderError",
    "MissingPromptTemplateError",
    "InvalidPromptTemplateError",
    "PromptVariableMismatchError",
    "PromptTemplateSpec",
    "build_prompt_template",
    "build_context_variables",
]
