"""Unit tests for Australian recogniser checksum functions and validate_result.

All tests are pure — no engine, no network, no spaCy. The checksum functions
and validate_result are tested directly against known-valid and known-invalid
values from the relevant authority (ATO, ASIC, Services Australia).
"""

import pytest

from priveil.recognisers.au_abn import AUABNRecogniser, _abn_checksum
from priveil.recognisers.au_acn import AUACNRecogniser, _acn_checksum
from priveil.recognisers.au_medicare import AUMedicareRecogniser, _medicare_checksum
from priveil.recognisers.au_tfn import AUTFNRecogniser, _tfn_checksum

# ── TFN ───────────────────────────────────────────────────────────────────────

class TestTFNChecksum:
    def test_valid_tfn(self) -> None:
        # 123 456 782: weights sum = 1+8+9+28+25+48+42+72+20 = 253... let me verify
        # 1*1+2*4+3*3+4*7+5*5+6*8+7*6+8*9+2*10 = 1+8+9+28+25+48+42+72+20 = 253
        # 253 % 11 = 0 (253 = 23*11) ✓
        assert _tfn_checksum([1, 2, 3, 4, 5, 6, 7, 8, 2]) is True

    def test_wrong_check_digit(self) -> None:
        assert _tfn_checksum([1, 2, 3, 4, 5, 6, 7, 8, 0]) is False

    def test_too_short(self) -> None:
        assert _tfn_checksum([1, 2, 3, 4, 5, 6, 7, 8]) is False

    def test_too_long(self) -> None:
        assert _tfn_checksum([1, 2, 3, 4, 5, 6, 7, 8, 2, 9]) is False


class TestTFNValidateResult:
    recogniser = AUTFNRecogniser()

    def test_valid_returns_true(self) -> None:
        # validate_result must return True (not None) so presidio keeps the match
        assert self.recogniser.validate_result("123 456 782") is True

    def test_invalid_returns_false_not_none(self) -> None:
        # The spike bug: returning None here means presidio keeps the match at
        # its original score. We must return False to invalidate.
        result = self.recogniser.validate_result("123 456 789")
        assert result is False, f"Expected False, got {result!r} — validate_result must not return None on failure"


# ── ABN ───────────────────────────────────────────────────────────────────────

class TestABNChecksum:
    def test_valid_abn(self) -> None:
        # 51 824 753 556 — ATO's own ABN, a canonical valid example
        assert _abn_checksum([5, 1, 8, 2, 4, 7, 5, 3, 5, 5, 6]) is True

    def test_wrong_digit(self) -> None:
        assert _abn_checksum([5, 1, 8, 2, 4, 7, 5, 3, 5, 5, 7]) is False

    def test_too_short(self) -> None:
        assert _abn_checksum([5, 1, 8, 2, 4, 7, 5, 3, 5, 5]) is False


class TestABNValidateResult:
    recogniser = AUABNRecogniser()

    def test_valid_returns_true(self) -> None:
        assert self.recogniser.validate_result("51 824 753 556") is True

    def test_invalid_returns_false_not_none(self) -> None:
        result = self.recogniser.validate_result("51 824 753 999")
        assert result is False


# ── ACN ───────────────────────────────────────────────────────────────────────

class TestACNChecksum:
    def test_valid_acn(self) -> None:
        # 004 085 616 — well-known valid ACN (BHP Billiton)
        # weights [8,7,6,5,4,3,2,1] applied to first 8 digits
        # 0*8+0*7+4*6+0*5+8*4+5*3+6*2+1*1 = 0+0+24+0+32+15+12+1 = 84
        # (10 - 84%10) % 10 = (10-4)%10 = 6 → check digit = 6 ✓
        assert _acn_checksum([0, 0, 4, 0, 8, 5, 6, 1, 6]) is True

    def test_wrong_check_digit(self) -> None:
        assert _acn_checksum([0, 0, 4, 0, 8, 5, 6, 1, 7]) is False

    def test_too_short(self) -> None:
        assert _acn_checksum([0, 0, 4, 0, 8, 5, 6, 1]) is False


class TestACNValidateResult:
    recogniser = AUACNRecogniser()

    def test_valid_returns_true(self) -> None:
        assert self.recogniser.validate_result("004 085 616") is True

    def test_invalid_returns_false_not_none(self) -> None:
        result = self.recogniser.validate_result("004 085 617")
        assert result is False


# ── Medicare ──────────────────────────────────────────────────────────────────

class TestMedicareChecksum:
    def test_valid_medicare(self) -> None:
        # Construct a valid number: first 8 digits + checksum + issue number
        digits_1_8 = [2, 1, 2, 3, 4, 5, 6, 7]
        weights = [1, 3, 7, 9, 1, 3, 7, 9]
        check = sum(d * w for d, w in zip(digits_1_8, weights)) % 10
        assert _medicare_checksum(digits_1_8 + [check, 9]) is True

    def test_wrong_check_digit(self) -> None:
        digits = [2, 1, 2, 3, 4, 5, 6, 7, 1, 9]
        assert _medicare_checksum(digits) is False

    def test_minimum_length_9_digits_supported(self) -> None:
        digits = [2, 1, 2, 3, 4, 5, 6, 7]
        checksum = sum(d * w for d, w in zip(digits, [1, 3, 7, 9, 1, 3, 7, 9])) % 10
        assert _medicare_checksum(digits + [checksum]) is True

    def test_too_short(self) -> None:
        assert _medicare_checksum([2, 1, 2, 3, 4, 5, 6, 7]) is False


class TestMedicareValidateResult:
    recogniser = AUMedicareRecogniser()

    def test_invalid_returns_false_not_none(self) -> None:
        result = self.recogniser.validate_result("2123 45671 9")
        assert result is False


class TestTFNLegacyHandling:
    recogniser = AUTFNRecogniser()

    def test_legacy_8_digit_tfn_is_excluded(self) -> None:
        assert self.recogniser.validate_result("12 345 678") is False


# ── Cross-cutting: validate_result never returns None on failure ───────────────

@pytest.mark.parametrize("recogniser,invalid_text", [
    (AUTFNRecogniser(), "123 456 789"),
    (AUABNRecogniser(), "51 824 753 999"),
    (AUACNRecogniser(), "004 085 617"),
])
def test_validate_result_returns_false_not_none_on_invalid(
    recogniser: object, invalid_text: str
) -> None:
    """validate_result must return False (not None) for invalid inputs.

    Returning None would tell presidio 'no validation performed' and the
    match would be kept at its original score — a critical correctness bug.
    """
    result = recogniser.validate_result(invalid_text)  # type: ignore[union-attr]
    assert result is False, (
        f"{type(recogniser).__name__}.validate_result({invalid_text!r}) returned "
        f"{result!r}; expected False so presidio invalidates the match"
    )
