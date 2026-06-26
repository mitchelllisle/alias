from presidio_analyzer import Pattern, PatternRecognizer


class AUPhoneRecogniser(PatternRecognizer):
    """Detect Australian mobile and landline phone numbers.

    Supplements the standard presidio PHONE_NUMBER recogniser with AU-specific
    patterns for local formats (04XX, +61 4XX, (0X) XXXX XXXX).
    """

    PATTERNS = [
        Pattern(
            "AU_PHONE_mobile",
            r"\b(?:\+61\s?|0)4\d{2}[\s\-]?\d{3}[\s\-]?\d{3}\b",
            0.75,
        ),
        Pattern(
            "AU_PHONE_landline",
            r"\b(?:\(0[2-9]\)\s?|0[2-9][\s\-]?)\d{4}[\s\-]?\d{4}\b",
            0.65,
        ),
    ]
    CONTEXT = ["phone", "mobile", "call", "contact", "tel", "telephone", "number"]

    def __init__(self) -> None:
        super().__init__(
            supported_entity="AU_PHONE",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
        )
