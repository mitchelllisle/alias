import hashlib
from typing import Literal

from pydantic import BaseModel, Field

from alias.domain.entities import Entity


class DetectionRequest(BaseModel, frozen=True):
    """Request to detect PII entities in text."""

    text: str = Field(..., min_length=1, description="Text to analyse")
    # Only English is supported in the current engine configuration.
    # Expand this Literal when multi-language support is added.
    language: Literal["en"] = Field(default="en", description="ISO 639-1 language code")
    mode: Literal["fast", "accurate"] = Field(
        default="accurate",
        description=(
            "'accurate' runs an LLM pass to remove false positives (slower). "
            "'fast' skips the LLM and returns raw detector output. "
            "No-ops to 'fast' when no judge model is configured."
        ),
    )


class DetectionResult(BaseModel, frozen=True):
    """Detected entities with a SHA-256 audit hash of the original input."""

    entities: tuple[Entity, ...]
    input_hash: str

    @classmethod
    def from_text(cls, text: str, entities: list[Entity]) -> "DetectionResult":
        """Build a DetectionResult with a stable audit hash of the input text.

        Args:
            text: The original input string.
            entities: Detected entities in any order.

        Returns:
            DetectionResult with entities sorted by start offset and a sha256 hash.
        """
        input_hash = "sha256:" + hashlib.sha256(text.encode()).hexdigest()
        sorted_entities = tuple(sorted(entities, key=lambda e: e.start))
        return cls(entities=sorted_entities, input_hash=input_hash)
