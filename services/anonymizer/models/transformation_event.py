"""Models describing anonymization transformation events."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TransformationEvent(BaseModel):
    """Summary of a single anonymization transformation."""

    entity_type: str = Field(..., description="Presidio entity type that was transformed.")
    action: str = Field(..., description="Anonymization operator that was applied.")
    start: int = Field(..., ge=0, description="Inclusive starting character index of the transformation.")
    end: int = Field(..., ge=0, description="Exclusive ending character index of the transformation.")
    surrogate: str = Field(
        ...,
        description=(
            "Preview of the surrogate value emitted by the anonymizer. "
            "Must not contain raw PHI."
        ),
    )

    class Config:
        frozen = True
        anystr_strip_whitespace = True
