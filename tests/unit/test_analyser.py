"""Unit tests for the async analyser engine.

_to_entity is a pure function — tested directly with real RecognizerResult objects.
AsyncAnalyser.analyse is tested against a real (small) spaCy-backed engine.
No mocks.
"""

from presidio_analyzer.recognizer_result import RecognizerResult

from priveil.domain.detection import DetectionRequest
from priveil.domain.entities import EntityType
from priveil.engine.analyser import AsyncAnalyser, _to_entity

# ── _to_entity ────────────────────────────────────────────────────────────────

def _result(entity_type: str, start: int, end: int, score: float = 0.85) -> RecognizerResult:
    return RecognizerResult(entity_type=entity_type, start=start, end=end, score=score)


def test_to_entity_known_type() -> None:
    text = "hello@example.com is the address"
    result = _to_entity(_result("EMAIL_ADDRESS", 0, 17), text)
    assert result is not None
    assert result.entity_type == EntityType.EMAIL_ADDRESS
    assert result.text == "hello@example.com"
    assert result.start == 0
    assert result.end == 17
    assert result.is_pii is True
    assert result.sensitivity == "medium"


def test_to_entity_unknown_type_returns_none() -> None:
    result = _to_entity(_result("UK_NHS", 0, 10), "some text here")
    assert result is None


def test_to_entity_score_rounded_to_4dp() -> None:
    result = _to_entity(_result("PERSON", 0, 4, score=0.123456789), "Jane is here")
    assert result is not None
    assert result.score == 0.1235


def test_to_entity_credit_card_is_critical() -> None:
    text = "4111111111111111 is the card"
    result = _to_entity(_result("CREDIT_CARD", 0, 16), text)
    assert result is not None
    assert result.sensitivity == "critical"
    assert result.is_pii is True


# ── AsyncAnalyser ─────────────────────────────────────────────────────────────

async def test_analyse_detects_email(analyser: AsyncAnalyser) -> None:
    req = DetectionRequest(text="Contact us at support@example.com for help.")
    result = await analyser.analyse(req)
    types = {e.entity_type for e in result.entities}
    assert EntityType.EMAIL_ADDRESS in types


async def test_analyse_input_hash_is_stable(analyser: AsyncAnalyser) -> None:
    req = DetectionRequest(text="hello world")
    r1 = await analyser.analyse(req)
    r2 = await analyser.analyse(req)
    assert r1.input_hash == r2.input_hash
    assert r1.input_hash.startswith("hmac-sha256:")


async def test_analyse_entities_sorted_by_start(analyser: AsyncAnalyser) -> None:
    req = DetectionRequest(text="Email jane@x.com or call 0412 345 678 today.")
    result = await analyser.analyse(req)
    starts = [e.start for e in result.entities]
    assert starts == sorted(starts)


async def test_analyse_no_critical_pii_in_clean_text(analyser: AsyncAnalyser) -> None:
    req = DetectionRequest(text="The fixed interest rate is 5.5 percent per annum.")
    result = await analyser.analyse(req)
    critical = [e for e in result.entities if e.sensitivity == "critical"]
    assert len(critical) == 0
