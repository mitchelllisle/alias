from fastapi import APIRouter

from alias.api.deps import AnalyserDep, RefinerDep
from alias.domain.detection import DetectionRequest, DetectionResult
from alias.judge.refiner import refine

router = APIRouter()


@router.post("", response_model=DetectionResult, summary="Detect PII entities in text")
async def detect(
    request: DetectionRequest,
    analyser: AnalyserDep,
    refiner: RefinerDep,
) -> DetectionResult:
    """Run entity detection on the provided text.

    Returns detected entities with type, offsets, confidence, PII classification,
    and sensitivity level. Includes a SHA-256 audit hash of the input.

    When mode='judge' (default) and a judge model is configured, an LLM pass
    removes false positives before returning. mode='fast' skips the LLM entirely.
    """
    result = await analyser.analyse(request)
    if request.mode == "judge" and refiner is not None:
        result = await refine(result, request.text, refiner)
    return result
