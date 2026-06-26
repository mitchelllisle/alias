from typing import Literal

from pydantic import BaseModel, Field

from alias.domain.detection import DetectionResult


class EntityBreakdown(BaseModel, frozen=True):
    """Aggregated count of a single entity type present in the text."""

    entity_type: str
    sensitivity: str
    count: int


class AssessmentRequest(BaseModel, frozen=True):
    """Request to assess the risk profile of a piece of text."""

    text: str = Field(..., min_length=1)
    detections: DetectionResult | None = Field(
        default=None,
        description="Pre-computed detections; omit to auto-detect",
    )
    context: str | None = Field(
        default=None,
        description="Optional domain context, e.g. 'Australian home loan application'",
    )


class AssessmentResult(BaseModel, frozen=True):
    """Risk profile of a piece of text.

    Produced by the LLM assessor; entity_breakdown is computed from detections.
    """

    overall_sensitivity: Literal["low", "medium", "high", "critical"]
    risk_summary: str = Field(description="One or two sentence plain-English summary of the risk")
    categories: list[str] = Field(description="Risk categories present, e.g. ['identity', 'financial']")
    regulatory_flags: list[str] = Field(
        description="Applicable Australian regulatory frameworks, e.g. ['Privacy Act s16B']"
    )
    recommended_handling: str = Field(description="Concrete handling guidance for this content")
    entity_breakdown: list[EntityBreakdown]
    reasoning: str
