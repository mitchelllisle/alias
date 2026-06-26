from fastapi import APIRouter

from alias.api.deps import AnalyserDep, AssessorDep
from alias.domain.assessment import AssessmentRequest, AssessmentResult
from alias.domain.detection import DetectionRequest
from alias.judge.assessor import assess

router = APIRouter()


@router.post("", response_model=AssessmentResult, summary="Assess content risk and sensitivity")
async def assess_content(
    request: AssessmentRequest,
    analyser: AnalyserDep,
    assessor: AssessorDep,
) -> AssessmentResult:
    """Assess the risk profile of a piece of text.

    Returns an overall sensitivity tier, risk categories, applicable Australian
    regulatory frameworks, recommended handling guidance, and a per-entity-type
    breakdown. Requires ALIAS_JUDGE_MODEL to be configured.

    Pass pre-computed detections to avoid running the detector twice.
    """
    detections = request.detections
    if detections is None:
        detections = await analyser.analyse(DetectionRequest(text=request.text))
    return await assess(request, detections, assessor)
