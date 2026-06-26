"""Judge service layer.

LLM adapter types (NewEntity, JudgeDecision) and the two pure transforms
(build_prompt, decision_to_result) live here.  The route and agent modules
import only from this module — no underscored cross-module imports.
"""

import json

from pydantic import BaseModel, Field

from alias.domain.detection import DetectionResult
from alias.domain.entities import ENTITY_CLASSIFICATION, Entity, EntityType
from alias.domain.judgement import JudgementRequest, JudgementResult


class NewEntity(BaseModel):
    """A missed entity surfaced by the judge.

    Field names match what the LLM is instructed to emit so the structured
    output parser maps cleanly without aliases.
    """

    text: str = Field(description="Exact text span from the original input")
    entity_type: str = Field(description="Entity type string, e.g. 'AU_TFN'")
    start: int = Field(description="Start character offset in the original text")
    end: int = Field(description="End character offset (exclusive)")
    score: float = Field(default=0.85, ge=0.0, le=1.0)


class JudgeDecision(BaseModel):
    """Raw structured output returned by the pydantic-ai agent.

    Intentionally simpler than JudgementResult — the LLM only expresses
    *changes*, not the full reconstructed entity list.
    """

    reasoning: str = Field(description="Step-by-step explanation of changes made and why")
    false_positive_indices: list[int] = Field(
        default_factory=list,
        description="Zero-based indices into detections.entities that are false positives",
    )
    false_negatives: list[NewEntity] = Field(
        default_factory=list,
        description="Entities present in the text that the detector missed",
    )


def build_prompt(request: JudgementRequest) -> str:
    """Render the per-request judge prompt from a JudgementRequest.

    Args:
        request: The judgement request with text, detections, and optional context.

    Returns:
        A formatted prompt string ready for the agent.
    """
    entities_json = json.dumps(
        [
            {
                "index": i,
                "text": e.text,
                "entity_type": e.entity_type.value,
                "start": e.start,
                "end": e.end,
                "score": e.score,
                "is_pii": e.is_pii,
                "sensitivity": e.sensitivity,
            }
            for i, e in enumerate(request.detections.entities)
        ],
        indent=2,
    )
    context_line = f"\nContext: {request.context}" if request.context else ""
    return f"""Review the following PII detections for accuracy.{context_line}

Original text:
\"\"\"
{request.text}
\"\"\"

Detected entities (zero-based index):
{entities_json}

Return your decision as structured JSON."""


def decision_to_result(decision: JudgeDecision, request: JudgementRequest) -> JudgementResult:
    """Convert a JudgeDecision to a JudgementResult.

    Pure transform — no I/O, no agent calls.

    Args:
        decision: Raw LLM decision with fp indices and new entity definitions.
        request: The original judgement request.

    Returns:
        JudgementResult with adjusted DetectionResult, removed/added lists, reasoning.
    """
    all_entities = list(request.detections.entities)
    fp_indices = set(decision.false_positive_indices)

    removed = [all_entities[i] for i in sorted(fp_indices) if i < len(all_entities)]
    kept = [e for i, e in enumerate(all_entities) if i not in fp_indices]

    added: list[Entity] = []
    for new_e in decision.false_negatives:
        try:
            entity_type = EntityType(new_e.entity_type)
        except ValueError:
            continue  # judge hallucinated an unknown type — drop silently
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

    adjusted = DetectionResult.from_text(text=request.text, entities=kept + added)
    return JudgementResult(
        adjusted=adjusted,
        removed=removed,
        added=added,
        reasoning=decision.reasoning,
    )
