import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from alias.api.deps import JudgeDep
from alias.domain.judgement import JudgementRequest, JudgementResult
from alias.judge.service import build_prompt, decision_to_result

router = APIRouter()


@router.post("", response_model=JudgementResult, summary="LLM judge: refine detection results")
async def judge(request: JudgementRequest, agent: JudgeDep) -> JudgementResult:
    """Run the LLM judge over a detection result.

    The judge reviews each entity for false positives and surfaces any missed
    entities (false negatives). Returns an adjusted DetectionResult with reasoning.

    Requires ALIAS_JUDGE_MODEL to be set (e.g. 'openai:gpt-4o').
    """
    prompt = build_prompt(request)
    result = await agent.run(prompt)
    return decision_to_result(result.output, request)


async def _sse_stream(request: JudgementRequest, agent: JudgeDep) -> AsyncIterator[str]:
    """Run the judge and emit results as SSE events.

    Structured output_type means token-level streaming is unavailable — we run
    the agent to completion and emit two SSE events:
        reasoning_chunk  — the judge's reasoning string
        result           — the full JudgementResult JSON
    """
    prompt = build_prompt(request)
    result = await agent.run(prompt)
    judgement = decision_to_result(result.output, request)

    payload = json.dumps({"text": judgement.reasoning})
    yield f"event: reasoning_chunk\ndata: {payload}\n\n"
    yield f"event: result\ndata: {judgement.model_dump_json()}\n\n"


@router.post(
    "/stream",
    summary="LLM judge: stream reasoning + result as SSE",
    response_class=StreamingResponse,
)
async def judge_stream(request: JudgementRequest, agent: JudgeDep) -> StreamingResponse:
    """Stream the LLM judge response as Server-Sent Events.

    Emits two events in sequence:
        reasoning_chunk — the judge's reasoning text.
        result          — final JudgementResult JSON.

    Note: token-level streaming is not available for structured output_type.
    Requires ALIAS_JUDGE_MODEL to be set.
    """
    return StreamingResponse(
        _sse_stream(request, agent),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
