"""Internal refinement domain types.

Not exposed on the API surface — used by the refiner to clean detections
before they are returned from /detect and /pseudonymise.
"""

from pydantic import BaseModel

from alias.domain.detection import DetectionResult
from alias.domain.entities import Entity


class JudgementRequest(BaseModel, frozen=True):
    text: str
    detections: DetectionResult
    context: str | None = None


class JudgementResult(BaseModel, frozen=True):
    adjusted: DetectionResult
    removed: list[Entity]
    added: list[Entity]
    reasoning: str
