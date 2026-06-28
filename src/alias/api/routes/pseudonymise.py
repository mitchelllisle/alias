from fastapi import APIRouter

from alias.api.deps import AnalyserDep, PseudonymiserDep, RefinerDep
from alias.domain.detection import DetectionRequest
from alias.domain.pseudonymisation import PseudonymisationRequest, PseudonymisationResult
from alias.judge.refiner import refine

router = APIRouter()


@router.post("", response_model=PseudonymisationResult, summary="Pseudonymise PII in text")
async def pseudonymise(
    request: PseudonymisationRequest,
    analyser: AnalyserDep,
    pseudonymiser: PseudonymiserDep,
    refiner: RefinerDep,
) -> PseudonymisationResult:
    """Pseudonymise PII entities in text using the configured operator strategies.

    If detections are omitted, detection runs automatically.
    When mode='judge' (default) and a judge model is configured, detections are
    refined by an LLM before pseudonymisation. mode='fast' skips the LLM entirely.
    Use operator_overrides to change the default strategy per entity type.
    """
    detections = request.detections
    if detections is None:
        detections = await analyser.analyse(DetectionRequest(text=request.text))
    if request.mode == "judge" and refiner is not None:
        detections = await refine(detections, request.text, refiner)
    return await pseudonymiser.pseudonymise(
        PseudonymisationRequest(
            text=request.text,
            detections=detections,
            operator_overrides=request.operator_overrides,
            mode="fast",  # LLM refinement already applied above; do not re-run
        )
    )
