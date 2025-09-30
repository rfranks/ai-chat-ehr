"""Utilities for configuring Microsoft Presidio analyzers.

This module centralizes construction of the :class:`~presidio_analyzer.AnalyzerEngine`
used by the anonymizer service.  We start from Presidio's built-in recognizers and
extend them with domain specific ones for facility names and insurance member IDs.
"""
from __future__ import annotations

from typing import Iterable, Optional, Sequence

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_analyzer.nlp_engine import NlpEngine
from presidio_analyzer.recognizer_registry import RecognizerRegistry

__all__ = [
    "build_analyzer_engine",
    "build_registry",
]

# Facility names follow predictable suffixes (Hospital, Clinic, Medical Center, etc.)
# The regex looks for a capitalized word optionally preceded by "St." and followed
# by one of these suffixes.  Context words reinforce that these spans correspond to
# healthcare facilities.
_FACILITY_PATTERNS: Sequence[Pattern] = (
    Pattern(
        name="facility_suffix",
        regex=r"\b(?:St\.?\s)?[A-Z][\w'&.-]{1,40}\s(?:Hospital|Clinic|Medical Center|Health Center|Urgent Care|Medical Group)\b",
        score=0.7,
    ),
)
_FACILITY_CONTEXT = ["hospital", "clinic", "medical", "center", "facility", "care"]

# Member identifiers typically mix uppercase letters and digits and appear alongside
# key phrases such as "member ID" or "subscriber number".  The regex avoids matching
# very short sequences to reduce false positives.
_MEMBER_ID_PATTERNS: Sequence[Pattern] = (
    Pattern(
        name="member_id_alphanumeric",
        regex=r"\b[A-Z]{2,5}[0-9]{4,10}\b",
        score=0.5,
    ),
    Pattern(
        name="member_id_mixed",
        regex=r"\b[0-9]{2,4}[A-Z]{2,5}[0-9]{2,6}\b",
        score=0.5,
    ),
)
_MEMBER_ID_CONTEXT = [
    "member",
    "subscriber",
    "policy",
    "plan",
    "beneficiary",
    "id",
    "number",
]


def _build_facility_name_recognizer() -> PatternRecognizer:
    """Return a recognizer for hospital and clinic names."""

    return PatternRecognizer(
        supported_entity="FACILITY_NAME",
        name="FacilityNameRecognizer",
        patterns=list(_FACILITY_PATTERNS),
        context=list(_FACILITY_CONTEXT),
    )


def _build_member_id_recognizer() -> PatternRecognizer:
    """Return a recognizer for insurance member identifiers."""

    return PatternRecognizer(
        supported_entity="MEMBER_ID",
        name="MemberIdRecognizer",
        patterns=list(_MEMBER_ID_PATTERNS),
        context=list(_MEMBER_ID_CONTEXT),
    )


def build_registry(additional_recognizers: Optional[Iterable[PatternRecognizer]] = None) -> RecognizerRegistry:
    """Create a :class:`RecognizerRegistry` with Presidio defaults and custom ones."""

    registry = RecognizerRegistry()
    registry.load_predefined_recognizers()

    for recognizer in (_build_facility_name_recognizer(), _build_member_id_recognizer()):
        registry.add_recognizer(recognizer)

    if additional_recognizers:
        for recognizer in additional_recognizers:
            registry.add_recognizer(recognizer)

    return registry


def build_analyzer_engine(
    *,
    nlp_engine: Optional[NlpEngine] = None,
    recognizers: Optional[Iterable[PatternRecognizer]] = None,
) -> AnalyzerEngine:
    """Construct an :class:`AnalyzerEngine` preloaded with recognizers.

    Parameters
    ----------
    nlp_engine:
        Optional Presidio NLP engine.  Tests may provide lightweight stubs to avoid
        loading heavyweight spaCy or Stanza models.  When ``None`` Presidio will
        lazily create an engine based on its default configuration.
    recognizers:
        Optional additional recognizers to register alongside the built-ins.
    """

    registry = build_registry(additional_recognizers=recognizers)
    return AnalyzerEngine(registry=registry, nlp_engine=nlp_engine)
