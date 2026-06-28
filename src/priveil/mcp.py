"""MCP server exposing priveil's PII tools to LLM clients.

Run as a stdio server:
    uv run python -m priveil.mcp

Then point Claude Desktop / Cursor / any MCP client at this command.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Literal, cast

from mcp.server.fastmcp import Context, FastMCP
from presidio_anonymizer import AnonymizerEngine
from pydantic_ai import Agent

from priveil.domain.assessment import AssessmentRequest, AssessmentResult
from priveil.domain.detection import DetectionRequest, DetectionResult
from priveil.domain.pseudonymisation import OperatorType, PseudonymisationRequest, PseudonymisationResult
from priveil.engine.analyser import AsyncAnalyser, build_analyser_engine
from priveil.engine.pseudonymiser import AsyncPseudonymiser
from priveil.judge.assessor import AssessmentDecision, assess as _assess
from priveil.judge.refiner import RefinerDecision, refine as _refine
from priveil.recognisers.registry import build_recognisers
from priveil.settings import Settings


@dataclass
class _State:
    analyser: AsyncAnalyser
    pseudonymiser: AsyncPseudonymiser
    refiner: Agent[None, RefinerDecision] | None
    assessor: Agent[None, AssessmentDecision] | None
    executor: ThreadPoolExecutor


@asynccontextmanager
async def _lifespan(server: FastMCP) -> AsyncIterator[_State]:
    settings = Settings()
    executor = ThreadPoolExecutor(max_workers=settings.executor_max_workers)
    engine = build_analyser_engine(
        spacy_model=settings.spacy_model,
        extra_recognisers=build_recognisers(),
    )
    refiner: Agent[None, RefinerDecision] | None = None
    assessor: Agent[None, AssessmentDecision] | None = None
    if settings.judge_model or settings.judge_base_url:
        from priveil.judge.assessor import build_assessor_agent
        from priveil.judge.refiner import build_refiner_agent

        refiner = build_refiner_agent(settings)
        assessor = build_assessor_agent(settings)

    state = _State(
        analyser=AsyncAnalyser(engine, executor),
        pseudonymiser=AsyncPseudonymiser(AnonymizerEngine(), executor),  # type: ignore[no-untyped-call]
        refiner=refiner,
        assessor=assessor,
        executor=executor,
    )
    try:
        yield state
    finally:
        executor.shutdown(wait=True)


mcp = FastMCP("priveil", lifespan=_lifespan)


def _state(ctx: Context) -> _State:  # type: ignore[type-arg]
    # FastMCP types lifespan_context as object; cast is safe — _lifespan yields _State.
    return cast(_State, ctx.request_context.lifespan_context)


@mcp.tool()
async def detect(
    text: str,
    ctx: Context,  # type: ignore[type-arg]
    mode: Literal["fast", "judge"] = "fast",
) -> DetectionResult:
    """Detect PII entities in text.

    Args:
        text: The text to scan for PII.
        mode: 'fast' for raw detector output; 'judge' adds an LLM pass to
            remove false positives (requires PRIVEIL_JUDGE_MODEL).

    Returns:
        Detected entities with type, offsets, confidence, PII flag, sensitivity,
        and a SHA-256 audit hash of the input.
    """
    state = _state(ctx)
    result = await state.analyser.analyse(DetectionRequest(text=text, mode=mode))
    if mode == "judge" and state.refiner is not None:
        result = await _refine(result, text, state.refiner)
    return result


@mcp.tool()
async def anonymise(
    text: str,
    ctx: Context,  # type: ignore[type-arg]
    mode: Literal["fast", "judge"] = "fast",
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
    state = _state(ctx)
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
    state = _state(ctx)
    if state.assessor is None:
        raise ValueError("assess requires PRIVEIL_JUDGE_MODEL to be configured.")
    detections = await state.analyser.analyse(DetectionRequest(text=text))
    return await _assess(AssessmentRequest(text=text, context=context), detections, state.assessor)


if __name__ == "__main__":
    mcp.run()
