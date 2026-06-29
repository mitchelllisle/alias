"""MCP tool definitions for priveil — detect, anonymise, assess.

Tools are registered on the shared ``mcp`` instance from ``server.py``.
Import this module to trigger registration; it is safe to import multiple times.
"""

from __future__ import annotations

import logging
from typing import Literal, cast

from mcp.server.fastmcp import Context

from priveil.domain.assessment import AssessmentRequest, AssessmentResult
from priveil.domain.detection import DetectionRequest, DetectionResult
from priveil.domain.pseudonymisation import OperatorType, PseudonymisationRequest, PseudonymisationResult
from priveil.judge.assessor import assess as _assess
from priveil.judge.refiner import refine as _refine
from priveil.mcp.server import get_state, mcp

logger = logging.getLogger(__name__)


@mcp.tool()
async def detect(
    text: str,
    ctx: Context,  # type: ignore[type-arg]  # conduit: FastMCP Context not generic at runtime
    mode: Literal["fast", "judge"] = "judge",
) -> DetectionResult:
    """Detect PII entities in text.

    Args:
        text: The text to scan for PII.
        mode: 'fast' for raw detector output; 'judge' adds an LLM pass to
            remove false positives. Falls back to 'fast' when PRIVEIL_JUDGE_MODEL
            is unset (surfaced via mode_used).

    Returns:
        Detected entities with type, offsets, confidence, PII flag, sensitivity,
        and an HMAC-SHA-256 audit hash of the input.
    """
    state = get_state(ctx)
    result = await state.analyser.analyse(DetectionRequest(text=text, mode=mode))
    mode_used = mode
    if mode == "judge" and state.refiner is not None:
        result = await _refine(result, text, state.refiner)
    elif mode == "judge":
        mode_used = "fast"
        logger.warning(
            "mode='judge' requested for MCP detect but PRIVEIL_JUDGE_MODEL is unset; falling back to mode='fast'."
        )
    result = result.model_copy(update={"mode_used": mode_used})
    return result


@mcp.tool()
async def anonymise(
    text: str,
    ctx: Context,  # type: ignore[type-arg]  # conduit: FastMCP Context not generic at runtime
    mode: Literal["fast", "judge"] = "judge",
    operator_overrides: dict[str, str] | None = None,
) -> PseudonymisationResult:
    """Replace detected PII with consistent placeholders.

    Args:
        text: The text to pseudonymise.
        mode: 'fast' or 'judge' — see detect.
        operator_overrides: Per-entity-type strategy overrides. Keys are entity
            type strings (e.g. 'PERSON', 'AU_TFN'); values are 'replace',
            'mask', 'redact', or 'hash'.

    Returns:
        Anonymised text and an entity_map of original PII spans to replacements.
        The entity_map is sensitive — protect it with the same controls as the
        original text.
    """
    state = get_state(ctx)
    detections = await state.analyser.analyse(DetectionRequest(text=text, mode=mode))
    mode_used = mode
    if mode == "judge" and state.refiner is not None:
        detections = await _refine(detections, text, state.refiner)
    elif mode == "judge":
        mode_used = "fast"
        logger.warning(
            "mode='judge' requested for MCP anonymise but PRIVEIL_JUDGE_MODEL is unset; falling back to mode='fast'."
        )
    _VALID_OPERATORS = {"replace", "mask", "redact", "hash"}
    if invalid := {v for v in (operator_overrides or {}).values() if v not in _VALID_OPERATORS}:
        raise ValueError(f"Invalid operator(s): {invalid}. Must be one of {_VALID_OPERATORS}.")
    overrides = {k: cast(OperatorType, v) for k, v in (operator_overrides or {}).items()}
    return (await state.pseudonymiser.pseudonymise(
        PseudonymisationRequest(
            text=text,
            detections=detections,
            operator_overrides=overrides,
            mode="fast",  # refinement already applied above
        )
    )).model_copy(update={"mode_requested": mode, "mode_used": mode_used})


@mcp.tool()
async def assess(
    text: str,
    ctx: Context,  # type: ignore[type-arg]  # conduit: FastMCP Context not generic at runtime
    context: str | None = None,
) -> AssessmentResult:
    """Assess the sensitivity and regulatory risk of text.

    Args:
        text: The text to assess.
        context: Optional document type or use case description
            (e.g. 'Australian home loan application') to improve accuracy.

    Returns:
        Sensitivity tier, risk categories, applicable Australian regulatory
        frameworks, recommended handling guidance, and a per-entity breakdown.

    Raises:
        ValueError: If PRIVEIL_JUDGE_MODEL is not configured.
    """
    state = get_state(ctx)
    if state.assessor is None:
        raise ValueError("assess requires PRIVEIL_JUDGE_MODEL to be configured.")
    detections = await state.analyser.analyse(DetectionRequest(text=text))
    return await _assess(AssessmentRequest(text=text, context=context), detections, state.assessor)
