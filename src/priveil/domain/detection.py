import hmac
import secrets
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field

from priveil.domain.entities import Entity


@lru_cache(maxsize=1)
def _process_audit_hash_key() -> bytes:
    """Return a process-scoped fallback HMAC key for audit hashing."""
    return secrets.token_bytes(32)


class DetectionRequest(BaseModel, frozen=True):
    """Request to detect PII entities in text."""

    text: str = Field(..., min_length=1, description="Text to analyse")
    # Only English is supported in the current engine configuration.
    # Expand this Literal when multi-language support is added.
    language: Literal["en"] = Field(default="en", description="ISO 639-1 language code")
    mode: Literal["fast", "judge"] = Field(
        default="judge",
        description=(
            "'judge' runs an LLM pass to remove false positives (slower). "
            "'fast' skips the LLM and returns raw detector output. "
            "Falls back to 'fast' when no judge model is configured (surfaced via mode_used)."
        ),
    )


class DetectionResult(BaseModel, frozen=True):
    """Detected entities with an HMAC-SHA-256 audit hash of the original input."""

    entities: tuple[Entity, ...]
    input_hash: str
    mode_requested: Literal["fast", "judge"] = "fast"
    mode_used: Literal["fast", "judge"] = "fast"

    @classmethod
    def from_text(
        cls,
        text: str,
        entities: list[Entity],
        mode_requested: Literal["fast", "judge"] = "fast",
        mode_used: Literal["fast", "judge"] = "fast",
        hash_key: bytes | None = None,
    ) -> "DetectionResult":
        """Build a DetectionResult with an HMAC-SHA-256 audit hash of the input text.

        Args:
            text: The original input string.
            entities: Detected entities in any order.
            mode_requested: Request mode supplied by the caller.
            mode_used: Effective mode used to produce this result.
            hash_key: Optional audit hash key; when omitted, a process-local key is used.

        Returns:
            DetectionResult with entities sorted by start offset and an HMAC digest.
        """
        key = hash_key or _process_audit_hash_key()
        input_hash = "hmac-sha256:" + hmac.new(key, text.encode(), "sha256").hexdigest()
        sorted_entities = tuple(sorted(entities, key=lambda e: e.start))
        return cls(
            entities=sorted_entities,
            input_hash=input_hash,
            mode_requested=mode_requested,
            mode_used=mode_used,
        )
