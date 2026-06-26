from pydantic import BaseModel, Field

from alias.domain.detection import DetectionResult
from alias.domain.entities import Entity


class JudgementRequest(BaseModel, frozen=True):
    """Request for the LLM judge to review and refine a detection result."""

    text: str = Field(..., min_length=1)
    detections: DetectionResult
    context: str | None = Field(
        default=None,
        description=(
            "Optional domain context for the judge, "
            "e.g. 'Australian retail banking loan document'"
        ),
    )


class JudgementResult(BaseModel, frozen=True):
    """LLM-refined detection result with provenance."""

    adjusted: DetectionResult
    removed: list[Entity]  # false positives the judge dropped
    added: list[Entity]  # false negatives the judge surfaced
    reasoning: str
