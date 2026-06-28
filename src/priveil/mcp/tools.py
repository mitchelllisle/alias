"""MCP tool definitions for priveil — detect, anonymise, assess.

Tools are registered on the shared ``mcp`` instance from ``server.py``.
Import this module to trigger registration; it is safe to import multiple times.
"""

from __future__ import annotations

from typing import Literal, cast

from mcp.server.fastmcp import Context

from priveil.domain.assessment import AssessmentRequest, AssessmentResult
from priveil.domain.detection import DetectionRequest, DetectionResult
from priveil.domain.pseudonymisation import OperatorType, PseudonymisationRequest, PseudonymisationResult
from priveil.judge.assessor import assess as _assess
from priveil.judge.refiner import refine as _refine
from priveil.mcp.server import get_state, mcp


@mcp.tool()
async def detect(
    text: str,
    ctx: Context,  # type: ignore[type-arg]
    mode: Literal["fast", "judge"] = "judge",
) -> DetectionResult:
    """Detect PII entities in text.

    Args:
        text: The text to scan for PII.
        mode: 'fast' for raw detector output; 'judge' adds an LLM pass to
            remove false positives. No-ops to 'fast' when PRIVEIL_JUDGE_MODEL
            is unset — no configuration change required.

    Returns:
        Detected entities with type, offsets, confidence, PII flag, sensitivity,
        and a SHA-256 audit hash of the input.
    """
    state = get_state(ctx)
    result = await state.analyser.analyse(DetectionRequest(text=text, mode=mode))
    if mode == "judge" and state.refiner is not None:
        result = await _refine(result, text, state.refiner)
    return result


@mcp.tool()
async def anonymise(
    text: str,
    ctx: Context,  # type: ignore[type-arg]
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
    if mode == "judge" and state.refiner is not None:
        detections = await _refine(detections, text, state.refiner)
    # OperatorType is a Literal alias; cast validates intent without runtime overhead.
    overrides = {k: cast(OperatorType, v) for k, v in (operator_overrides or {}).items()}
    return await state.pseudonymiser.pseudonymise(
        PseudonymisationRequest(
            text=text,
            detections=detections,
            operator_overrides=overrides,
            mode="fast",  # refinement already applied above
        )
    )


@mcp.tool()
async def assess(
    text: str,
    ctx: Context,  # type: ignore[type-arg]
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
