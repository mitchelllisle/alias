"""MCP tool definitions for priveil — detect, anonymise, assess.

Tools are registered on the shared ``mcp`` instance from ``server.py``.
Import this module to trigger registration; it is safe to import multiple times.
"""

from __future__ import annotations

import logging
from typing import Literal, cast

from mcp.server.fastmcp import Context

from priveil.api.models import Meta, PriveilResponse, RequestMeta, ResponseMeta
from priveil.domain.assessment import AssessmentData, AssessmentRequest
from priveil.domain.detection import DetectionData, DetectionRequest
from priveil.domain.pseudonymisation import OperatorType, PseudonymisationData, PseudonymisationRequest
from priveil.judge.assessor import ASSESSMENT_ADVISORY_DISCLAIMER
from priveil.judge.assessor import assess as _assess
from priveil.mcp.server import get_state, mcp

logger = logging.getLogger(__name__)


@mcp.tool()
async def detect(
    text: str,
    ctx: Context,  # type: ignore[type-arg]  # conduit: FastMCP Context not generic at runtime
    mode: Literal["fast", "judge"] = "judge",
) -> PriveilResponse[DetectionData]:
    """Detect PII entities in text.

    Args:
        text: The text to analyse for PII.
        mode: 'judge' runs an LLM pass to remove false positives (slower, default).
            'fast' returns raw detector output. Falls back to 'fast' when
            PRIVEIL_JUDGE_MODEL is unset (surfaced via meta.response.mode).

    Returns:
        PriveilResponse with meta (request/response mode and input_hash) and
        data containing the list of detected entities.
    """
    state = get_state(ctx)
    result = await state.analyser.analyse(DetectionRequest(text=text, mode=mode))
    mode_used = mode
    judge_applied = False
    if mode == "judge" and state.refiner is not None:
        refined = await state.refiner.refine(text, result.entities)
        result = result.model_copy(update={"entities": refined.entities})
        judge_applied = refined.judge_applied
    elif mode == "judge":
        mode_used = "fast"
        logger.warning(
            "mode='judge' requested for MCP detect but PRIVEIL_JUDGE_MODEL is unset; falling back to mode='fast'."
        )
    return PriveilResponse(
        meta=Meta(
            request=RequestMeta(mode=mode),
            response=ResponseMeta(mode=mode_used, input_hash=result.input_hash),
        ),
        data=DetectionData(entities=result.entities, judge_applied=judge_applied),
    )


@mcp.tool()
async def anonymise(
    text: str,
    ctx: Context,  # type: ignore[type-arg]  # conduit: FastMCP Context not generic at runtime
    mode: Literal["fast", "judge"] = "judge",
    operator_overrides: dict[str, str] | None = None,
) -> PriveilResponse[PseudonymisationData]:
    """Replace detected PII with consistent placeholders.

    Args:
        text: The text to pseudonymise.
        mode: 'fast' or 'judge' — see detect.
        operator_overrides: Per-entity-type strategy overrides. Keys are entity
            type strings (e.g. 'PERSON', 'AU_TFN'); values are 'replace',
            'mask', 'redact', or 'hash'.

    Returns:
        PriveilResponse with meta and data containing anonymised_text and
        entity_map of original PII spans to replacements.
        The entity_map is sensitive — protect it with the same controls as the
        original text.
    """
    state = get_state(ctx)
    detections = await state.analyser.analyse(DetectionRequest(text=text, mode=mode))
    input_hash = detections.input_hash
    mode_used = mode
    judge_applied = False
    if mode == "judge" and state.refiner is not None:
        refined = await state.refiner.refine(text, detections.entities)
        detections = detections.model_copy(update={"entities": refined.entities})
        judge_applied = refined.judge_applied
    elif mode == "judge":
        mode_used = "fast"
        logger.warning(
            "mode='judge' requested for MCP anonymise but PRIVEIL_JUDGE_MODEL is unset; falling back to mode='fast'."
        )
    _VALID_OPERATORS = {"replace", "mask", "redact", "hash"}
    if invalid := {v for v in (operator_overrides or {}).values() if v not in _VALID_OPERATORS}:
        raise ValueError(f"Invalid operator(s): {invalid}. Must be one of {_VALID_OPERATORS}.")
    overrides = {k: cast(OperatorType, v) for k, v in (operator_overrides or {}).items()}
    result = await state.pseudonymiser.pseudonymise(
        PseudonymisationRequest(
            text=text,
            detections=DetectionData(entities=detections.entities),
            operator_overrides=overrides,
            mode="fast",  # refinement already applied above
        )
    )
    return PriveilResponse(
        meta=Meta(
            request=RequestMeta(mode=mode),
            response=ResponseMeta(mode=mode_used, input_hash=input_hash),
        ),
        data=result.model_copy(update={"judge_applied": judge_applied}),
    )


@mcp.tool()
async def assess(
    text: str,
    ctx: Context,  # type: ignore[type-arg]  # conduit: FastMCP Context not generic at runtime
    context: str | None = None,
) -> PriveilResponse[AssessmentData]:
    """Assess the sensitivity and regulatory risk of text.

    Args:
        text: The text to assess.
        context: Optional document type or use case description
            (e.g. 'Australian home loan application') to improve accuracy.

    Returns:
        PriveilResponse with meta (input_hash and advisory_disclaimer) and
        data containing sensitivity tier, risk categories, applicable Australian
        regulatory frameworks, recommended handling guidance, and a per-entity breakdown.

    Raises:
        ValueError: If PRIVEIL_JUDGE_MODEL is not configured.
    """
    state = get_state(ctx)
    if state.assessor is None:
        raise ValueError("assess requires PRIVEIL_JUDGE_MODEL to be configured.")
    detections = await state.analyser.analyse(DetectionRequest(text=text))
    data = await _assess(AssessmentRequest(text=text, context=context), detections, state.assessor)
    return PriveilResponse(
        meta=Meta(
            request=RequestMeta(),
            response=ResponseMeta(
                input_hash=detections.input_hash,
                advisory_disclaimer=ASSESSMENT_ADVISORY_DISCLAIMER,
            ),
        ),
        data=data,
    )
