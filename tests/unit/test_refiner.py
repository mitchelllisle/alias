"""Unit tests for alias.judge.refiner — pure functions only, no I/O."""


from alias.domain.detection import DetectionResult
from alias.domain.entities import ENTITY_CLASSIFICATION, Entity, EntityType
from alias.domain.judgement import JudgementRequest
from alias.judge.refiner import RefinerDecision, _apply_decision, _NewEntity


def _entity(entity_type: EntityType, text: str, start: int = 0) -> Entity:
    is_pii, sensitivity = ENTITY_CLASSIFICATION[entity_type]
    return Entity(
        text=text, entity_type=entity_type,
        start=start, end=start + len(text),
        score=0.9, is_pii=is_pii, sensitivity=sensitivity,
    )


def _req(*entities: Entity, text: str = "test") -> JudgementRequest:
    return JudgementRequest(
        text=text,
        detections=DetectionResult.from_text(text=text, entities=list(entities)),
    )


# ── no changes ────────────────────────────────────────────────────────────────

def test_no_changes_passthrough() -> None:
    entity = _entity(EntityType.EMAIL_ADDRESS, "a@b.com")
    req = _req(entity, text="Email a@b.com here")
    decision = RefinerDecision(reasoning="all good")
    result = _apply_decision(decision, req)
    assert len(result.adjusted.entities) == 1
    assert result.removed == []
    assert result.added == []


# ── false positive removal ────────────────────────────────────────────────────

def test_false_positive_removed() -> None:
    # from_text sorts by start — DATE_TIME (start=17) → index 1, PERSON (start=0) → index 0
    person = _entity(EntityType.PERSON, "Jane Smith", start=0)
    fp = _entity(EntityType.DATE_TIME, "4.5%", start=17)
    req = _req(person, fp, text="Jane Smith earns 4.5%")
    decision = RefinerDecision(reasoning="rate not a date", false_positive_indices=[1])
    result = _apply_decision(decision, req)
    assert len(result.removed) == 1
    assert result.removed[0].text == "4.5%"
    assert len(result.adjusted.entities) == 1
    assert result.adjusted.entities[0].text == "Jane Smith"


def test_out_of_range_fp_index_ignored() -> None:
    entity = _entity(EntityType.PERSON, "Alice")
    req = _req(entity, text="Alice here")
    decision = RefinerDecision(reasoning="ok", false_positive_indices=[99])
    result = _apply_decision(decision, req)
    assert len(result.adjusted.entities) == 1
    assert result.removed == []


# ── false negative addition ───────────────────────────────────────────────────

def test_false_negative_added() -> None:
    req = _req(text="TFN is 123 456 782")
    decision = RefinerDecision(
        reasoning="TFN missed",
        false_negatives=[_NewEntity(text="123 456 782", entity_type="AU_TFN", start=7, end=18)],
    )
    result = _apply_decision(decision, req)
    assert len(result.added) == 1
    assert result.added[0].entity_type == EntityType.AU_TFN
    assert result.added[0].sensitivity == "critical"


def test_hallucinated_entity_type_silently_dropped() -> None:
    req = _req(text="some text")
    decision = RefinerDecision(
        reasoning="found one",
        false_negatives=[_NewEntity(text="some", entity_type="NOT_REAL", start=0, end=4)],
    )
    result = _apply_decision(decision, req)
    assert result.added == []


def test_negative_fp_index_rejected() -> None:
    """Python's -1 index would silently remove the last entity — must be blocked."""
    entity = _entity(EntityType.PERSON, "Alice")
    req = _req(entity, text="Alice here")
    decision = RefinerDecision(reasoning="bad index", false_positive_indices=[-1])
    result = _apply_decision(decision, req)
    assert result.removed == []
    assert len(result.adjusted.entities) == 1


def test_fn_out_of_bounds_start_dropped() -> None:
    req = _req(text="hello")
    decision = RefinerDecision(
        reasoning="bad offsets",
        false_negatives=[_NewEntity(text="hello", entity_type="PERSON", start=-1, end=5)],
    )
    assert _apply_decision(decision, req).added == []


def test_fn_out_of_bounds_end_dropped() -> None:
    req = _req(text="hello")
    decision = RefinerDecision(
        reasoning="bad offsets",
        false_negatives=[_NewEntity(text="hello", entity_type="PERSON", start=0, end=99)],
    )
    assert _apply_decision(decision, req).added == []


def test_fn_span_mismatch_dropped() -> None:
    """text[start:end] must equal new_e.text exactly — wrong text rejected."""
    req = _req(text="hello world")
    decision = RefinerDecision(
        reasoning="wrong span",
        false_negatives=[_NewEntity(text="world!", entity_type="PERSON", start=6, end=11)],
    )
    assert _apply_decision(decision, req).added == []


def test_fn_start_ge_end_dropped() -> None:
    req = _req(text="hello")
    decision = RefinerDecision(
        reasoning="bad offsets",
        false_negatives=[_NewEntity(text="", entity_type="PERSON", start=3, end=3)],
    )
    assert _apply_decision(decision, req).added == []
