from presidio_analyzer import Pattern, PatternRecognizer


class AUBSBRecogniser(PatternRecognizer):
    """Detect Australian Bank State Branch (BSB) codes.

    Format: XXX-XXX (hyphen required). No checksum — BSB is a routing lookup.
    Low base score; context words are required to reach a meaningful threshold.
    """

    PATTERNS = [
        Pattern("AU_BSB", r"\b\d{3}-\d{3}\b", 0.5),
    ]
    CONTEXT = ["bsb", "bank state branch", "branch number", "routing", "bank code"]

    def __init__(self) -> None:
        super().__init__(
            supported_entity="AU_BSB",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
        )
