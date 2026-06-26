"""Unit tests for alias.judge.service.

Pure functions (build_prompt, decision_to_result) — no I/O, no agent, no mocks.
"""

import pytest
from pydantic import ValidationError

from alias.domain.detection import DetectionResult
from alias.domain.entities import ENTITY_CLASSIFICATION, Entity, EntityType
from alias.domain.judgement import JudgementRequest
from alias.judge.service import JudgeDecision, NewEntity, build_prompt, decision_to_result


def _entity(entity_type: EntityType, text: str, start: int = 0) -> Entity:
    is_pii, sensitivity = ENTITY_CLASSIFICATION[entity_type]
    return Entity(
        text=text,
        entity_type=entity_type,
        start=start,
        end=start + len(text),
        score=0.9,
        is_pii=is_pii,
        sensitivity=sensitivity,
    )


def _request(*entities: Entity, text: str = "test text", context: str | None = None) -> JudgementRequest:
    detections = DetectionResult.from_text(text=text, entities=list(entities))
    return JudgementRequest(text=text, detections=detections, context=context)


# ── build_prompt ──────────────────────────────────────────────────────────────

def test_build_prompt_contains_text() -> None:
    req = _request(text="Send to jane@example.com")
    prompt = build_prompt(req)
    assert "Send to jane@example.com" in prompt


def test_build_prompt_contains_entity_index() -> None:
    entity = _entity(EntityType.PERSON, "Jane Smith", start=0)
    req = _request(entity, text="Jane Smith called")
    prompt = build_prompt(req)
    assert '"index": 0' in prompt
    assert '"text": "Jane Smith"' in prompt


def test_build_prompt_includes_context() -> None:
    req = _request(text="Some text", context="Australian retail banking")
    assert "Australian retail banking" in build_prompt(req)


def test_build_prompt_no_context_line_when_absent() -> None:
    req = _request(text="Some text")
    assert "Context:" not in build_prompt(req)


def test_build_prompt_empty_entities_still_valid() -> None:
    req = _request(text="The rate is 4.5% p.a.")
    prompt = build_prompt(req)
    assert "[]" in prompt  # empty entities array


# ── decision_to_result — no changes ──────────────────────────────────────────

def test_no_changes_returns_same_entities() -> None:
    entity = _entity(EntityType.EMAIL_ADDRESS, "a@b.com")
    req = _request(entity, text="Email a@b.com here")
    decision = JudgeDecision(reasoning="All correct", false_positive_indices=[], false_negatives=[])
    result = decision_to_result(decision, req)
    assert len(result.adjusted.entities) == 1
    assert result.removed == []
    assert result.added == []
    assert result.reasoning == "All correct"


# ── decision_to_result — false positives ─────────────────────────────────────

def test_false_positive_removed() -> None:
    # DetectionResult.from_text sorts entities by start position.
    # e1 (start=0) becomes index 0, e0 (start=12) becomes index 1.
    e0 = _entity(EntityType.DATE_TIME, "4.5%", start=12)
    e1 = _entity(EntityType.PERSON, "Jane Smith", start=0)
    req = _request(e0, e1, text="Jane Smith earns 4.5%")
    decision = JudgeDecision(reasoning="4.5% is a rate not a date", false_positive_indices=[1])
    result = decision_to_result(decision, req)
    assert len(result.removed) == 1
    assert result.removed[0].text == "4.5%"
    assert len(result.adjusted.entities) == 1
    assert result.adjusted.entities[0].text == "Jane Smith"


def test_out_of_range_fp_index_ignored() -> None:
    entity = _entity(EntityType.PERSON, "Alice")
    req = _request(entity, text="Alice here")
    decision = JudgeDecision(reasoning="ok", false_positive_indices=[99])
    result = decision_to_result(decision, req)
    assert len(result.adjusted.entities) == 1
    assert result.removed == []


# ── decision_to_result — false negatives ─────────────────────────────────────

def test_false_negative_added() -> None:
    req = _request(text="TFN is 123 456 782")
    decision = JudgeDecision(
        reasoning="TFN was missed",
        false_negatives=[NewEntity(text="123 456 782", entity_type="AU_TFN", start=7, end=18)],
    )
    result = decision_to_result(decision, req)
    assert len(result.added) == 1
    assert result.added[0].entity_type == EntityType.AU_TFN
    assert result.added[0].is_pii is True
    assert result.added[0].sensitivity == "critical"


def test_hallucinated_entity_type_dropped() -> None:
    req = _request(text="some text")
    decision = JudgeDecision(
        reasoning="found one",
        false_negatives=[NewEntity(text="some", entity_type="MADE_UP_TYPE", start=0, end=4)],
    )
    result = decision_to_result(decision, req)
    assert result.added == []
    assert len(result.adjusted.entities) == 0


def test_false_negative_classification_comes_from_map() -> None:
    req = _request(text="Medicare 2123 45670 3")
    decision = JudgeDecision(
        reasoning="Medicare missed",
        false_negatives=[NewEntity(text="2123 45670 3", entity_type="AU_MEDICARE", start=9, end=21)],
    )
    result = decision_to_result(decision, req)
    assert result.added[0].sensitivity == "critical"
    assert result.added[0].is_pii is True


# ── JudgementResult type shape ────────────────────────────────────────────────

def test_result_is_frozen() -> None:
    entity = _entity(EntityType.PERSON, "Bob")
    req = _request(entity, text="Bob here")
    decision = JudgeDecision(reasoning="fine")
    result = decision_to_result(decision, req)
    with pytest.raises((TypeError, AttributeError, ValidationError)):
        result.reasoning = "mutated"  # type: ignore[misc]
