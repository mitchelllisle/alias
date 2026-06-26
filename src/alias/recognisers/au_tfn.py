from presidio_analyzer import Pattern, PatternRecognizer

# ATO-published weights for the 9-digit TFN checksum (mod 11).
_TFN_WEIGHTS: tuple[int, ...] = (1, 4, 3, 7, 5, 8, 6, 9, 10)


def _tfn_checksum(digits: list[int]) -> bool:
    """Validate a 9-digit TFN using the ATO mod-11 checksum.

    Args:
        digits: Exactly 9 integers extracted from the candidate string.

    Returns:
        True if the weighted sum is divisible by 11, False otherwise.
    """
    if len(digits) != 9:
        return False
    return sum(d * w for d, w in zip(digits, _TFN_WEIGHTS)) % 11 == 0


class AUTFNRecogniser(PatternRecognizer):
    """Detect Australian Tax File Numbers (TFN).

    Two patterns:
    - Spaced (XXX XXX XXX) — high base score, checksum-validated.
    - Compact (9 digits) — low base score, requires context words to reach threshold.

    validate_result returns False (not None) on checksum failure so presidio
    correctly invalidates the match rather than keeping it at its original score.
    """

    PATTERNS = [
        Pattern("AU_TFN_spaced", r"\b\d{3}[ \t]\d{3}[ \t]\d{3}\b", 0.8),
        Pattern("AU_TFN_compact", r"\b\d{9}\b", 0.3),
    ]
    CONTEXT = ["tfn", "tax file", "tax file number", "taxfile", "tax-file"]

    def __init__(self) -> None:
        super().__init__(
            supported_entity="AU_TFN",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
        )

    def validate_result(self, pattern_text: str) -> bool | None:
        """Return True if checksum passes, False to invalidate — never None on failure."""
        digits = [int(c) for c in pattern_text if c.isdigit()]
        return _tfn_checksum(digits)
