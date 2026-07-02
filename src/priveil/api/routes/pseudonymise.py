import logging

from fastapi import APIRouter

from priveil.api.deps import AnalyserDep, PseudonymiserDep, RefinerDep
from priveil.api.models import Meta, PriveilResponse, RequestMeta, ResponseMeta
from priveil.domain.detection import DetectionData, DetectionRequest
from priveil.domain.pseudonymisation import PseudonymisationData, PseudonymisationRequest

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("", response_model=PriveilResponse[PseudonymisationData], summary="Pseudonymise PII in text")
async def pseudonymise(
    request: PseudonymisationRequest,
    analyser: AnalyserDep,
    pseudonymiser: PseudonymiserDep,
    refiner: RefinerDep,
) -> PriveilResponse[PseudonymisationData]:
    """Pseudonymise PII entities in text using the configured operator strategies.

    If detections are omitted, detection runs automatically.
    When mode='judge' (default) and a judge model is configured, detections are
    refined by an LLM before pseudonymisation. mode='fast' skips the LLM entirely.
    Use operator_overrides to change the default strategy per entity type.

    Pass ``body["data"]`` from a prior ``/detect`` response as ``detections``.
    """
    if request.detections is not None:
        # Reconstruct an internal DetectionResult (with stable hash) from the
        # API-visible DetectionData supplied by the client.
        detections = analyser.detections_from_entities(
            request.text, request.detections.entities, request.mode
        )
    else:
        detections = await analyser.analyse(DetectionRequest(text=request.text, mode=request.mode))

    input_hash = detections.input_hash
    mode_used = request.mode
    judge_applied = False
    if request.mode == "judge" and refiner is not None:
        refined = await refiner.refine(request.text, detections.entities)
        detections = detections.model_copy(update={"entities": refined.entities})
        judge_applied = refined.judge_applied
    elif request.mode == "judge":
        mode_used = "fast"
        logger.warning(
            "mode='judge' requested for /pseudonymise but PRIVEIL_JUDGE_MODEL is unset; falling back to mode='fast'."
        )

    result = await pseudonymiser.pseudonymise(
        PseudonymisationRequest(
            text=request.text,
            detections=DetectionData(entities=detections.entities),
            operator_overrides=request.operator_overrides,
            mode="fast",  # LLM refinement already applied above; do not re-run
        )
    )
    return PriveilResponse(
        meta=Meta(
            request=RequestMeta(mode=request.mode),
            response=ResponseMeta(mode=mode_used, input_hash=input_hash),
        ),
        data=result.model_copy(update={"judge_applied": judge_applied}),
    )
