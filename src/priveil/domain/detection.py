import hmac
import secrets
from typing import Literal

from pydantic import BaseModel, Field

from priveil.domain.entities import Entity


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
            "Falls back to 'fast' when no judge model is configured (surfaced via meta.response.mode)."
        ),
    )


class DetectionData(BaseModel, frozen=True):
    """API-visible detection payload — entities only.

    Used as the ``data`` field of ``PriveilResponse[DetectionData]``.
    Audit hash and mode tracking live in ``meta``.

    Also accepted as the ``detections`` input on ``/pseudonymise`` and ``/assess``;
    clients pass ``body["data"]`` from a prior ``/detect`` response.
    """

    entities: tuple[Entity, ...]
    judge_applied: bool = False


class DetectionResult(BaseModel, frozen=True):
    """Internal detection result — entities plus audit hash and mode metadata.

    Not exposed directly in API responses. Routes project this into
    ``PriveilResponse[DetectionData]`` and carry ``input_hash`` / mode into ``meta``.
    """

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
            hash_key: HMAC key; when omitted a one-off ephemeral key is used.
                      In production, always pass the engine's stable key so hashes
                      are consistent across requests.

        Returns:
            DetectionResult with entities sorted by start offset and an HMAC digest.
        """
        key = hash_key if hash_key is not None else secrets.token_bytes(32)
        input_hash = "hmac-sha256:" + hmac.new(key, text.encode(), "sha256").hexdigest()
        sorted_entities = tuple(sorted(entities, key=lambda e: e.start))
        return cls(
            entities=sorted_entities,
            input_hash=input_hash,
            mode_requested=mode_requested,
            mode_used=mode_used,
        )
