import asyncio
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig, RecognizerResult

from alias.domain.anonymisation import AnonymisationRequest, AnonymisationResult, OperatorType
from alias.domain.entities import Entity

# Default anonymisation strategy per entity type.
# Presidio-specific parameter names live here in the engine, not in the domain.
_DEFAULT_OPERATOR_CONFIGS: dict[str, tuple[str, dict[str, object]]] = {
    "PERSON": ("replace", {"new_value": "<PERSON>"}),
    "EMAIL_ADDRESS": ("replace", {"new_value": "<EMAIL>"}),
    "PHONE_NUMBER": ("replace", {"new_value": "<PHONE>"}),
    "CREDIT_CARD": ("mask", {"masking_char": "*", "chars_to_mask": 12, "from_end": False}),
    "LOCATION": ("replace", {"new_value": "<LOCATION>"}),
    "DATE_TIME": ("replace", {"new_value": "<DATE>"}),
    "NRP": ("replace", {"new_value": "<NRP>"}),
    "AU_TFN": ("replace", {"new_value": "***-***-***"}),
    "AU_ABN": ("replace", {"new_value": "** *** *** ***"}),
    "AU_ACN": ("replace", {"new_value": "*** *** ***"}),
    "AU_BSB": ("replace", {"new_value": "XXX-XXX"}),
    "AU_ACCOUNT_NUMBER": ("mask", {"masking_char": "*", "chars_to_mask": 6, "from_end": False}),
    "AU_MEDICARE": ("replace", {"new_value": "**** *****-*"}),
    "AU_PHONE": ("replace", {"new_value": "<PHONE>"}),
}


def _override_params(op_type: OperatorType, entity_type: str) -> dict[str, object]:
    """Return safe default params for per-request operator overrides."""
    if op_type == "replace":
        return {"new_value": f"<{entity_type}>"}
    if op_type == "mask":
        return {"masking_char": "*", "chars_to_mask": 100, "from_end": False}
    return {}


def _build_operators(overrides: dict[str, OperatorType]) -> dict[str, OperatorConfig]:
    """Merge default operator configs with per-request overrides.

    Args:
        overrides: entity_type → operator name, e.g. {'PERSON': 'redact'}.

    Returns:
        Dict of entity_type → OperatorConfig ready for presidio.
    """
    merged: dict[str, OperatorConfig] = {
        entity_type: OperatorConfig(op_name, params)
        for entity_type, (op_name, params) in _DEFAULT_OPERATOR_CONFIGS.items()
    }
    for entity_type, op_type in overrides.items():
        merged[entity_type] = OperatorConfig(op_type, _override_params(op_type, entity_type))
    return merged


def _to_recognizer_result(entity: Entity) -> RecognizerResult:
    """Convert a domain Entity to a presidio RecognizerResult for anonymisation."""
    return RecognizerResult(
        entity_type=entity.entity_type.value,
        start=entity.start,
        end=entity.end,
        score=entity.score,
    )


def _expected_replacement(entity: Entity, operators: dict[str, OperatorConfig]) -> str:
    """Compute the expected replacement string for an entity given its operator.

    For replace operators the replacement is known; for mask/hash/redact a label
    is returned. anonymised_text is always authoritative — this is for the audit map.

    Args:
        entity: The entity being anonymised.
        operators: Resolved operator config map.

    Returns:
        Expected replacement string or a descriptive label.
    """
    op = operators.get(entity.entity_type.value)
    if op is None:
        return entity.text
    if op.operator_name == "replace":
        return str(op.params.get("new_value", f"<{entity.entity_type.value}>"))
    if op.operator_name == "redact":
        return ""
    return f"<{entity.entity_type.value}:{op.operator_name}>"


def _build_entity_map(
    entities: Sequence[Entity],
    operators: dict[str, OperatorConfig],
) -> dict[str, str]:
    """Build an original-text → replacement audit map from entities and operators.

    Computed before presidio runs so the mapping is deterministic and not
    dependent on presidio's internal result ordering.

    Args:
        entities: Detected entities to be anonymised.
        operators: Resolved operator config map.

    Returns:
        Dict of original entity text → expected replacement.
    """
    return {e.text: _expected_replacement(e, operators) for e in entities}


class AsyncAnonymiser:
    """Async wrapper around presidio AnonymizerEngine, offloaded to a thread-pool executor."""

    def __init__(self, engine: AnonymizerEngine, executor: ThreadPoolExecutor) -> None:
        self._engine = engine
        self._executor = executor

    async def anonymise(self, request: AnonymisationRequest) -> AnonymisationResult:
        """Anonymise text using the entities from a DetectionResult.

        Args:
            request: AnonymisationRequest; detections must be populated by the caller.

        Returns:
            AnonymisationResult with anonymised text and audit entity_map.

        Raises:
            ValueError: if request.detections is None.
        """
        if request.detections is None:
            raise ValueError("detections must be populated before calling anonymise()")

        operators = _build_operators(request.operator_overrides)
        recognizer_results = [_to_recognizer_result(e) for e in request.detections.entities]
        entity_map = _build_entity_map(request.detections.entities, operators)

        loop = asyncio.get_running_loop()
        _run = partial(
            self._engine.anonymize,
            text=request.text,
            analyzer_results=recognizer_results,
            operators=operators,
        )
        result = await loop.run_in_executor(self._executor, _run)
        return AnonymisationResult(anonymised_text=result.text, entity_map=entity_map)
