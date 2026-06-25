from presidio_analyzer import Pattern, PatternRecognizer

# ATO mod-89 weights for the 11-digit ABN.
_ABN_WEIGHTS: tuple[int, ...] = (10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19)


def _abn_checksum(digits: list[int]) -> bool:
    """Validate an 11-digit ABN using the ATO mod-89 algorithm.

    Args:
        digits: Exactly 11 integers.

    Returns:
        True if (first digit − 1, rest unchanged) weighted sum is divisible by 89.
    """
    if len(digits) != 11:
        return False
    adjusted = [digits[0] - 1, *digits[1:]]
    return sum(d * w for d, w in zip(adjusted, _ABN_WEIGHTS)) % 89 == 0


class AUABNRecogniser(PatternRecognizer):
    """Detect Australian Business Numbers (ABN).

    ABN is an 11-digit business identifier — not personal PII but tracked as a
    financial entity. Compact pattern has a very low base score; context words
    or checksum are needed to pass the presidio threshold.
    """

    PATTERNS = [
        Pattern("AU_ABN_spaced", r"\b\d{2}[ \t]\d{3}[ \t]\d{3}[ \t]\d{3}\b", 0.8),
        Pattern("AU_ABN_compact", r"\b\d{11}\b", 0.25),
    ]
    CONTEXT = ["abn", "australian business number", "business number"]

    def __init__(self) -> None:
        super().__init__(
            supported_entity="AU_ABN",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
        )

    def validate_result(self, pattern_text: str) -> bool | None:
        """Return True if mod-89 checksum passes, False to invalidate."""
        digits = [int(c) for c in pattern_text if c.isdigit()]
        return _abn_checksum(digits)
