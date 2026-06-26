from fastapi import APIRouter

from alias.api.deps import AnalyserDep, AnonymiserDep
from alias.domain.anonymisation import AnonymisationRequest, AnonymisationResult
from alias.domain.detection import DetectionRequest

router = APIRouter()


@router.post("", response_model=AnonymisationResult, summary="Anonymise PII in text")
async def anonymise(
    request: AnonymisationRequest,
    analyser: AnalyserDep,
    anonymiser: AnonymiserDep,
) -> AnonymisationResult:
    """Anonymise PII entities in text using the configured operator strategies.

    If detections are omitted, detection runs automatically.
    Use operator_overrides to change the default strategy for a given entity type,
    e.g. {'PERSON': 'redact'} to fully remove names instead of replacing them.
    """
    detections = request.detections
    if detections is None:
        detections = await analyser.analyse(DetectionRequest(text=request.text))
        request = AnonymisationRequest(
            text=request.text,
            detections=detections,
            operator_overrides=request.operator_overrides,
        )
    return await anonymiser.anonymise(request)
