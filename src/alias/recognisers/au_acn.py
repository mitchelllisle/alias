from presidio_analyzer import Pattern, PatternRecognizer

# ASIC weights for the 9-digit ACN checksum (complement-of-10).
_ACN_WEIGHTS: tuple[int, ...] = (8, 7, 6, 5, 4, 3, 2, 1)


def _acn_checksum(digits: list[int]) -> bool:
    """Validate a 9-digit ACN using the ASIC complement-of-10 algorithm.

    Args:
        digits: Exactly 9 integers.

    Returns:
        True if (10 − weighted_sum % 10) % 10 == digits[8].
    """
    if len(digits) != 9:
        return False
    weighted_sum = sum(d * w for d, w in zip(digits[:8], _ACN_WEIGHTS))
    check = (10 - weighted_sum % 10) % 10
    return check == digits[8]


class AUACNRecogniser(PatternRecognizer):
    """Detect Australian Company Numbers (ACN).

    ACN is a 9-digit company identifier — not personal PII.
    """

    PATTERNS = [
        Pattern("AU_ACN_spaced", r"\b\d{3}[ \t]\d{3}[ \t]\d{3}\b", 0.7),
        Pattern("AU_ACN_compact", r"\b\d{9}\b", 0.25),
    ]
    CONTEXT = ["acn", "australian company number", "company number", "company no"]

    def __init__(self) -> None:
        super().__init__(
            supported_entity="AU_ACN",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
        )

    def validate_result(self, pattern_text: str) -> bool | None:
        """Return True if ASIC checksum passes, False to invalidate."""
        digits = [int(c) for c in pattern_text if c.isdigit()]
        return _acn_checksum(digits)
