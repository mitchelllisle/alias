"""Internal LLM refiner for /detect and /anonymise.

Not part of the public API surface. Takes a DetectionResult, asks the LLM
to remove false positives and surface false negatives, returns a cleaned
DetectionResult with the same schema.
"""

import json
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from alias.domain.detection import DetectionResult
from alias.domain.entities import ENTITY_CLASSIFICATION, Entity, EntityType
from alias.domain.judgement import JudgementRequest, JudgementResult

# ── LLM adapter type — shape the refiner agent must emit ─────────────────────

class _NewEntity(BaseModel):
    text: str = Field(description="Exact text span from the original input")
    entity_type: str = Field(description="Entity type string, e.g. 'AU_TFN'")
    start: int = Field(description="Start character offset in the original text")
    end: int = Field(description="End character offset (exclusive)")
    score: float = Field(default=0.85, ge=0.0, le=1.0)


class RefinerDecision(BaseModel):
    reasoning: str = Field(description="One sentence per change explaining why")
    false_positive_indices: list[int] = Field(
        default_factory=list,
        description="Zero-based indices into detections.entities that are false positives",
    )
    false_negatives: list[_NewEntity] = Field(
        default_factory=list,
        description="Entities present in the text that the detector missed",
    )


_PROMPTS_DIR = Path(__file__).parent / "prompts"
REFINER_SYSTEM_PROMPT: str = (_PROMPTS_DIR / "refiner.md").read_text(encoding="utf-8").strip()


def _build_refiner_prompt(request: JudgementRequest) -> str:
    entities_json = json.dumps(
        [
            {
                "index": i,
                "text": e.text,
                "entity_type": e.entity_type.value,
                "start": e.start,
                "end": e.end,
                "score": e.score,
            }
            for i, e in enumerate(request.detections.entities)
        ],
        indent=2,
    )
    return f"""Review these detections for false positives and missed PII.

Text:
\"\"\"{request.text}\"\"\"

Detected entities (zero-based index):
{entities_json}"""


def _apply_decision(decision: RefinerDecision, request: JudgementRequest) -> JudgementResult:
    """Apply a RefinerDecision to produce a JudgementResult. Pure function.

    Guards applied:
    - FP indices must be in [0, len(entities)) — negative indices are rejected.
    - FN spans must be in-bounds and the text slice must match new_e.text exactly.
    """
    text = request.text
    all_entities = list(request.detections.entities)
    n = len(all_entities)
    # Guard: reject negative indices and out-of-range indices.
    fp_indices = {i for i in decision.false_positive_indices if 0 <= i < n}

    removed = [all_entities[i] for i in sorted(fp_indices)]
    kept = [e for i, e in enumerate(all_entities) if i not in fp_indices]

    added: list[Entity] = []
    for new_e in decision.false_negatives:
        # Guard: reject invalid offsets and mismatched spans.
        if (
            new_e.start < 0
            or new_e.end > len(text)
            or new_e.start >= new_e.end
            or text[new_e.start : new_e.end] != new_e.text
        ):
            continue
        try:
            entity_type = EntityType(new_e.entity_type)
        except ValueError:
            continue
        is_pii, sensitivity = ENTITY_CLASSIFICATION[entity_type]
        added.append(
            Entity(
                text=new_e.text,
                entity_type=entity_type,
                start=new_e.start,
                end=new_e.end,
                score=new_e.score,
                is_pii=is_pii,
                sensitivity=sensitivity,
            )
        )

    adjusted = DetectionResult.from_text(text=text, entities=kept + added)
    return JudgementResult(adjusted=adjusted, removed=removed, added=added, reasoning=decision.reasoning)


def build_refiner_agent(model: str, temperature: float = 0.0) -> Agent[None, RefinerDecision]:
    """Build the internal refiner agent."""
    return Agent(
        model=model,
        output_type=RefinerDecision,
        system_prompt=REFINER_SYSTEM_PROMPT,
        model_settings={"temperature": temperature},
    )


async def refine(
    detections: DetectionResult,
    text: str,
    agent: Agent[None, RefinerDecision],
) -> DetectionResult:
    """Run the LLM refiner and return cleaned detections.

    Used internally by /detect and /anonymise when mode='accurate'.
    """
    req = JudgementRequest(text=text, detections=detections)
    prompt = _build_refiner_prompt(req)
    result = await agent.run(prompt)
    return _apply_decision(result.output, req).adjusted
