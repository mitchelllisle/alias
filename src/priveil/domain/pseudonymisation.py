from typing import Literal

from pydantic import BaseModel, Field

from priveil.domain.detection import DetectionData

# The set of pseudonymisation strategies understood by the engine.
# Intentionally a domain concept — engine translates these to presidio specifics.
OperatorType = Literal["replace", "mask", "redact", "hash"]


class PseudonymisationRequest(BaseModel, frozen=True):
    """Request to pseudonymise text.

    If detections is omitted, the API layer runs detection automatically first.
    operator_overrides replaces the default strategy for a given entity type.
    Pass ``body["data"]`` from a prior ``/detect`` response as ``detections``.
    """

    text: str = Field(..., min_length=1)
    detections: DetectionData | None = Field(
        default=None,
        description="Pre-computed detections; omit to auto-detect",
    )
    operator_overrides: dict[str, OperatorType] = Field(
        default_factory=dict,
        description="Override the default operator per entity type, e.g. {'PERSON': 'redact'}",
    )
    mode: Literal["fast", "judge"] = Field(
        default="judge",
        description=(
            "'judge' runs an LLM pass on detections before pseudonymising (slower). "
            "'fast' skips the LLM. Falls back to 'fast' when no judge model is configured "
            "(surfaced via meta.response.mode)."
        ),
    )


class PseudonymisationData(BaseModel, frozen=True):
    """Pseudonymised text with an audit map of original span → replacement.

    Used as the ``data`` field of ``PriveilResponse[PseudonymisationData]``.
    Mode tracking lives in ``meta``.

    ``anonymised_text`` is authoritative. ``entity_map`` is an approximation for
    audit / downstream use; for mask and hash operators the exact output
    is not knowable before pseudonymisation runs.
    """

    anonymised_text: str
    entity_map: dict[str, str]
    judge_applied: bool = False
