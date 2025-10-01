"""Pydantic response models exposed by the anonymizer API."""

from __future__ import annotations

from typing import Dict, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EntityActionSummary(BaseModel):
    """Summary of anonymization actions applied to a particular entity type."""

    count: int = Field(..., ge=0, description="Number of transformations for the entity type.")
    actions: Dict[str, int] = Field(
        default_factory=dict,
        description="Mapping of anonymization actions to their occurrence counts.",
    )


class TransformationAggregates(BaseModel):
    """Aggregated anonymization statistics across the processed document."""

    total_transformations: int = Field(
        ...,
        ge=0,
        description="Total number of transformation events collected during anonymization.",
    )
    actions: Dict[str, int] = Field(
        default_factory=dict,
        description="Mapping of anonymization actions to their overall occurrence counts.",
    )
    entities: Dict[str, EntityActionSummary] = Field(
        default_factory=dict,
        description="Per-entity breakdown of anonymization actions and counts.",
    )


class TransformationSummary(BaseModel):
    """Response payload summarizing anonymization activity for a patient document."""

    model_config = ConfigDict(populate_by_name=True)

    record_id: UUID = Field(
        ..., alias="recordId", description="Identifier of the persisted anonymized patient record."
    )
    transformations: TransformationAggregates = Field(
        ..., description="Aggregated statistics describing the transformation events."
    )


class AnonymizeResponse(BaseModel):
    """Standard response returned from the anonymization endpoint."""

    status: Literal["accepted"] = Field(
        ..., description="Status indicator that the anonymization request has been accepted."
    )
    summary: TransformationSummary = Field(
        ..., description="Summary of the anonymization results for the processed document."
    )


__all__ = [
    "EntityActionSummary",
    "TransformationAggregates",
    "TransformationSummary",
    "AnonymizeResponse",
]

