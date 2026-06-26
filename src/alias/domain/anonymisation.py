from typing import Literal

from pydantic import BaseModel, Field

from alias.domain.detection import DetectionResult

# The set of anonymisation strategies understood by the engine.
# Intentionally a domain concept — engine translates these to presidio specifics.
OperatorType = Literal["replace", "mask", "redact", "hash"]


class AnonymisationRequest(BaseModel, frozen=True):
    """Request to anonymise text.

    If detections is omitted, the API layer runs detection automatically first.
    operator_overrides replaces the default strategy for a given entity type.
    """

    text: str = Field(..., min_length=1)
    detections: DetectionResult | None = Field(
        default=None,
        description="Pre-computed detections; omit to auto-detect",
    )
    operator_overrides: dict[str, OperatorType] = Field(
        default_factory=dict,
        description="Override the default operator per entity type, e.g. {'PERSON': 'redact'}",
    )
    mode: Literal["fast", "accurate"] = Field(
        default="accurate",
        description=(
            "'accurate' runs an LLM pass on detections before anonymising (slower). "
            "'fast' skips the LLM. No-ops to 'fast' when no judge model is configured."
        ),
    )


class AnonymisationResult(BaseModel, frozen=True):
    """Anonymised text with an audit map of original span → replacement.

    anonymised_text is authoritative. entity_map is an approximation for
    audit / downstream use; for mask and hash operators the exact output
    is not knowable before anonymisation runs.
    """

    anonymised_text: str
    entity_map: dict[str, str]
