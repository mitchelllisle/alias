"""Unit tests for alias.judge.assessor — pure functions only."""

from alias.domain.assessment import AssessmentRequest
from alias.domain.detection import DetectionResult
from alias.domain.entities import ENTITY_CLASSIFICATION, Entity, EntityType
from alias.judge.assessor import _build_assessment_prompt, _entity_breakdown


def _entity(entity_type: EntityType, text: str, start: int = 0) -> Entity:
    is_pii, sensitivity = ENTITY_CLASSIFICATION[entity_type]
    return Entity(
        text=text, entity_type=entity_type,
        start=start, end=start + len(text),
        score=0.9, is_pii=is_pii, sensitivity=sensitivity,
    )


def _detections(*entities: Entity, text: str = "test") -> DetectionResult:
    return DetectionResult.from_text(text=text, entities=list(entities))


# ── _entity_breakdown ─────────────────────────────────────────────────────────

def test_breakdown_counts_by_type() -> None:
    detections = _detections(
        _entity(EntityType.PERSON, "Jane Smith"),
        _entity(EntityType.PERSON, "John Doe", start=15),
        _entity(EntityType.EMAIL_ADDRESS, "a@b.com", start=30),
        text="Jane Smith and John Doe at a@b.com",
    )
    breakdown = _entity_breakdown(detections)
    counts = {b.entity_type: b.count for b in breakdown}
    assert counts["PERSON"] == 2
    assert counts["EMAIL_ADDRESS"] == 1


def test_breakdown_excludes_non_pii() -> None:
    detections = _detections(
        _entity(EntityType.AU_ABN, "51 824 753 556"),  # is_pii=False
        _entity(EntityType.EMAIL_ADDRESS, "a@b.com", start=20),
        text="ABN 51 824 753 556 contact a@b.com",
    )
    breakdown = _entity_breakdown(detections)
    types = {b.entity_type for b in breakdown}
    assert "AU_ABN" not in types
    assert "EMAIL_ADDRESS" in types


def test_breakdown_empty_when_no_pii() -> None:
    detections = _detections(text="The rate is 4.5% p.a.")
    assert _entity_breakdown(detections) == []


def test_breakdown_sensitivity_from_classification() -> None:
    detections = _detections(
        _entity(EntityType.AU_TFN, "123 456 782"),
        text="TFN 123 456 782",
    )
    breakdown = _entity_breakdown(detections)
    assert breakdown[0].sensitivity == "critical"


# ── _build_assessment_prompt ──────────────────────────────────────────────────

def test_prompt_contains_text() -> None:
    req = AssessmentRequest(text="Call jane@example.com")
    detections = _detections(_entity(EntityType.EMAIL_ADDRESS, "jane@example.com"), text=req.text)
    prompt = _build_assessment_prompt(req, detections)
    assert "Call jane@example.com" in prompt


def test_prompt_excludes_non_pii_from_entities_list() -> None:
    req = AssessmentRequest(text="ABN 51 824 753 556")
    detections = _detections(_entity(EntityType.AU_ABN, "51 824 753 556"), text=req.text)
    prompt = _build_assessment_prompt(req, detections)
    # ABN is not PII — should be excluded from the entities list shown to the LLM
    assert "AU_ABN" not in prompt


def test_prompt_includes_context() -> None:
    req = AssessmentRequest(text="some text", context="Australian home loan")
    detections = _detections(text=req.text)
    assert "Australian home loan" in _build_assessment_prompt(req, detections)


def test_prompt_no_context_line_when_absent() -> None:
    req = AssessmentRequest(text="some text")
    detections = _detections(text=req.text)
    assert "Context:" not in _build_assessment_prompt(req, detections)
