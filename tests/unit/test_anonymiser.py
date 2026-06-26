"""Unit tests for the async anonymiser engine.

Pure functions (_build_entity_map, _expected_replacement, _to_recognizer_result)
are tested directly. AsyncAnonymiser is tested against the real presidio engine.
No mocks.
"""

from presidio_anonymizer.entities import OperatorConfig

from alias.domain.entities import ENTITY_CLASSIFICATION, Entity, EntityType
from alias.engine.anonymiser import (
    AsyncAnonymiser,
    _build_entity_map,
    _expected_replacement,
    _to_recognizer_result,
)


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


# ── _to_recognizer_result ─────────────────────────────────────────────────────

def test_to_recognizer_result_fields() -> None:
    entity = _entity(EntityType.EMAIL_ADDRESS, "a@b.com", start=5)
    result = _to_recognizer_result(entity)
    assert result.entity_type == "EMAIL_ADDRESS"
    assert result.start == 5
    assert result.end == 12
    assert result.score == 0.9


# ── _expected_replacement ─────────────────────────────────────────────────────

def test_replace_operator_returns_new_value() -> None:
    entity = _entity(EntityType.AU_TFN, "123 456 782")
    op = OperatorConfig("replace", {"new_value": "***-***-***"})
    assert _expected_replacement(entity, {"AU_TFN": op}) == "***-***-***"


def test_redact_operator_returns_empty_string() -> None:
    entity = _entity(EntityType.PERSON, "Jane Smith")
    op = OperatorConfig("redact", {})
    assert _expected_replacement(entity, {"PERSON": op}) == ""


def test_mask_operator_returns_label() -> None:
    entity = _entity(EntityType.CREDIT_CARD, "4111111111111111")
    op = OperatorConfig("mask", {"masking_char": "*", "chars_to_mask": 12, "from_end": False})
    result = _expected_replacement(entity, {"CREDIT_CARD": op})
    assert "CREDIT_CARD" in result


def test_no_operator_returns_original_text() -> None:
    entity = _entity(EntityType.LOCATION, "Sydney")
    assert _expected_replacement(entity, {}) == "Sydney"


# ── _build_entity_map ─────────────────────────────────────────────────────────

def test_build_entity_map_replace() -> None:
    entity = _entity(EntityType.AU_TFN, "123 456 782")
    op = OperatorConfig("replace", {"new_value": "***-***-***"})
    result = _build_entity_map([entity], {"AU_TFN": op})
    assert result == {"123 456 782": "***-***-***"}


def test_build_entity_map_multiple_entities() -> None:
    tfn = _entity(EntityType.AU_TFN, "123 456 782", start=0)
    email = _entity(EntityType.EMAIL_ADDRESS, "a@b.com", start=20)
    operators = {
        "AU_TFN": OperatorConfig("replace", {"new_value": "***-***-***"}),
        "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": "<EMAIL>"}),
    }
    result = _build_entity_map([tfn, email], operators)
    assert result["123 456 782"] == "***-***-***"
    assert result["a@b.com"] == "<EMAIL>"


def test_build_entity_map_empty_entities() -> None:
    assert _build_entity_map([], {}) == {}


# ── AsyncAnonymiser ───────────────────────────────────────────────────────────

async def test_anonymise_replaces_email(anonymiser: AsyncAnonymiser) -> None:
    from alias.domain.anonymisation import AnonymisationRequest
    from alias.domain.detection import DetectionResult

    entity = _entity(EntityType.EMAIL_ADDRESS, "jane@example.com", start=12)
    detections = DetectionResult.from_text("Send email to jane@example.com", [entity])
    req = AnonymisationRequest(text="Send email to jane@example.com", detections=detections)
    result = await anonymiser.anonymise(req)
    assert "jane@example.com" not in result.anonymised_text
    assert "<EMAIL>" in result.anonymised_text


async def test_anonymise_replaces_tfn(anonymiser: AsyncAnonymiser) -> None:
    from alias.domain.anonymisation import AnonymisationRequest
    from alias.domain.detection import DetectionResult

    entity = _entity(EntityType.AU_TFN, "123 456 782", start=7)
    detections = DetectionResult.from_text("TFN is 123 456 782", [entity])
    req = AnonymisationRequest(text="TFN is 123 456 782", detections=detections)
    result = await anonymiser.anonymise(req)
    assert "123 456 782" not in result.anonymised_text
    assert "***-***-***" in result.anonymised_text


async def test_anonymise_operator_override_redact(anonymiser: AsyncAnonymiser) -> None:
    from alias.domain.anonymisation import AnonymisationRequest
    from alias.domain.detection import DetectionResult

    entity = _entity(EntityType.PERSON, "Jane Smith", start=8)
    detections = DetectionResult.from_text("Contact Jane Smith today", [entity])
    req = AnonymisationRequest(
        text="Contact Jane Smith today",
        detections=detections,
        operator_overrides={"PERSON": "redact"},
    )
    result = await anonymiser.anonymise(req)
    assert "Jane Smith" not in result.anonymised_text


async def test_anonymise_no_entities_text_unchanged(anonymiser: AsyncAnonymiser) -> None:
    from alias.domain.anonymisation import AnonymisationRequest
    from alias.domain.detection import DetectionResult

    text = "Interest rate is 5.5% per annum."
    detections = DetectionResult.from_text(text, [])
    req = AnonymisationRequest(text=text, detections=detections)
    result = await anonymiser.anonymise(req)
    assert result.anonymised_text == text


async def test_anonymise_entity_map_populated(anonymiser: AsyncAnonymiser) -> None:
    from alias.domain.anonymisation import AnonymisationRequest
    from alias.domain.detection import DetectionResult

    entity = _entity(EntityType.AU_BSB, "062-000", start=4)
    detections = DetectionResult.from_text("BSB 062-000", [entity])
    req = AnonymisationRequest(text="BSB 062-000", detections=detections)
    result = await anonymiser.anonymise(req)
    assert "062-000" in result.entity_map
    assert result.entity_map["062-000"] == "XXX-XXX"
