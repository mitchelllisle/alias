from fastapi import APIRouter

from alias.api.deps import AnalyserDep, AnonymiserDep, RefinerDep
from alias.domain.anonymisation import AnonymisationRequest, AnonymisationResult
from alias.domain.detection import DetectionRequest
from alias.judge.refiner import refine

router = APIRouter()


@router.post("", response_model=AnonymisationResult, summary="Anonymise PII in text")
async def anonymise(
    request: AnonymisationRequest,
    analyser: AnalyserDep,
    anonymiser: AnonymiserDep,
    refiner: RefinerDep,
) -> AnonymisationResult:
    """Anonymise PII entities in text using the configured operator strategies.

    If detections are omitted, detection runs automatically.
    When mode='accurate' (default) and a judge model is configured, detections are
    refined by an LLM before anonymisation. mode='fast' skips the LLM entirely.
    Use operator_overrides to change the default strategy per entity type.
    """
    detections = request.detections
    if detections is None:
        detections = await analyser.analyse(DetectionRequest(text=request.text))
    if request.mode == "accurate" and refiner is not None:
        detections = await refine(detections, request.text, refiner)
    return await anonymiser.anonymise(
        AnonymisationRequest(
            text=request.text,
            detections=detections,
            operator_overrides=request.operator_overrides,
            mode="fast",  # LLM refinement already applied above; do not re-run
        )
    )
