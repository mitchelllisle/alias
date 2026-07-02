"""Internal span-verdict refiner for /detect and /pseudonymise."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel

from priveil.domain.entities import Entity

if TYPE_CHECKING:
    from openai import AsyncOpenAI

    from priveil.settings import Settings


class RefineResult(BaseModel, frozen=True):
    entities: tuple[Entity, ...]
    judge_applied: bool


_PROMPTS_DIR = Path(__file__).parent / "prompts"
REFINER_SYSTEM_PROMPT: str = (_PROMPTS_DIR / "refiner.md").read_text(encoding="utf-8").strip()
KEEP_SCHEMA = {
    "type": "object",
    "properties": {
        "keep": {"type": "array", "items": {"type": "integer"}},
    },
    "required": ["keep"],
    "additionalProperties": False,
}


class Refiner:
    def __init__(self, client: "AsyncOpenAI", settings: "Settings") -> None:
        self._client = client
        self._settings = settings

    async def refine(self, text: str, entities: tuple[Entity, ...]) -> RefineResult:
        s = self._settings
        certain: list[Entity] = []
        uncertain: list[Entity] = []

        for entity in entities:
            if entity.score >= s.judge_score_threshold or entity.entity_type.value not in s.judge_eligible_types:
                certain.append(entity)
            else:
                uncertain.append(entity)

        if not uncertain:
            return RefineResult(entities=tuple(certain), judge_applied=False)

        payload = [
            {
                "id": i,
                "type": entity.entity_type.value,
                "span": entity.text,
                "context": text[max(0, entity.start - s.judge_context_chars) : entity.end + s.judge_context_chars],
            }
            for i, entity in enumerate(uncertain)
        ]

        try:
            async with asyncio.timeout(s.judge_timeout_ms / 1000):
                keep_ids = await self._judge(payload)
        except (TimeoutError, Exception):
            return RefineResult(entities=tuple(certain + uncertain), judge_applied=False)

        kept = [entity for i, entity in enumerate(uncertain) if i in keep_ids]
        return RefineResult(entities=tuple(certain + kept), judge_applied=True)

    async def _judge(self, payload: list[dict[str, str | int]]) -> set[int]:
        model_name = self._settings.judge_model
        if not model_name:
            raise ValueError("PRIVEIL_JUDGE_MODEL must be set to use judge mode.")
        model_name = model_name.split(":", 1)[1] if ":" in model_name else model_name
        response = await self._client.chat.completions.create(
            model=model_name,
            max_tokens=self._settings.judge_max_tokens,
            temperature=0,
            messages=[
                {"role": "system", "content": REFINER_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload)},
            ],
            extra_body={"guided_json": KEEP_SCHEMA},
        )
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("Judge returned an empty response.")
        parsed = json.loads(content)
        keep = parsed.get("keep", [])
        return {int(i) for i in keep}


def build_refiner(settings: "Settings") -> Refiner:
    """Build the span-verdict refiner from settings."""
    from priveil.judge.model import build_judge_client

    return Refiner(client=build_judge_client(settings), settings=settings)

