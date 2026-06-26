from presidio_analyzer import Pattern, PatternRecognizer

# DVA/Services Australia weights for Medicare check digit (applied to digits 1–9).
_MEDICARE_WEIGHTS: tuple[int, ...] = (1, 3, 7, 9, 1, 3, 7, 9, 1)


def _medicare_checksum(digits: list[int]) -> bool:
    """Validate a Medicare card number using the Services Australia algorithm.

    Args:
        digits: At least 10 integers (11th digit is the IRN suffix, not checked here).

    Returns:
        True if sum(digits[0:9] * weights) mod 10 == digits[9].
    """
    if len(digits) < 10:
        return False
    weighted_sum = sum(d * w for d, w in zip(digits[:9], _MEDICARE_WEIGHTS))
    return weighted_sum % 10 == digits[9]


class AUMedicareRecogniser(PatternRecognizer):
    """Detect Australian Medicare card numbers.

    Format: XXXX XXXXX X (first digit 2–6, 10 digits total, last is check digit).
    Critical PII — government health identifier.
    """

    PATTERNS = [
        Pattern("AU_MEDICARE_spaced", r"\b[2-6]\d{3}[ \t]\d{5}[ \t]\d\b", 0.8),
        Pattern("AU_MEDICARE_compact", r"\b[2-6]\d{9}\b", 0.35),
    ]
    CONTEXT = ["medicare", "medicare number", "medicare card", "health insurance", "dva"]

    def __init__(self) -> None:
        super().__init__(
            supported_entity="AU_MEDICARE",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
        )

    def validate_result(self, pattern_text: str) -> bool | None:
        """Return True if checksum passes, False to invalidate."""
        digits = [int(c) for c in pattern_text if c.isdigit()]
        return _medicare_checksum(digits)
