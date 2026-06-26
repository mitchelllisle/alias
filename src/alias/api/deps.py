from typing import Annotated, cast

from fastapi import Depends, HTTPException, Request
from pydantic_ai import Agent

from alias.engine.analyser import AsyncAnalyser
from alias.engine.anonymiser import AsyncAnonymiser
from alias.judge.assessor import AssessmentDecision
from alias.judge.refiner import RefinerDecision


def _get_analyser(request: Request) -> AsyncAnalyser:
    return cast(AsyncAnalyser, request.app.state.analyser)


AnalyserDep = Annotated[AsyncAnalyser, Depends(_get_analyser)]

def _get_anonymiser(request: Request) -> AsyncAnonymiser:
    return cast(AsyncAnonymiser, request.app.state.anonymiser)


AnonymiserDep = Annotated[AsyncAnonymiser, Depends(_get_anonymiser)]


def _get_refiner(request: Request) -> "Agent[None, RefinerDecision] | None":
    return request.app.state.refiner  # type: ignore[no-any-return]


# Optional — routes silently skip refinement when this is None.
RefinerDep = Annotated["Agent[None, RefinerDecision] | None", Depends(_get_refiner)]


def _get_assessor(request: Request) -> "Agent[None, AssessmentDecision]":
    agent = request.app.state.assessor
    if agent is None:
        raise HTTPException(
            status_code=503,
            detail="Assessment not available — set ALIAS_JUDGE_MODEL to enable",
        )
    return agent  # type: ignore[no-any-return]


AssessorDep = Annotated["Agent[None, AssessmentDecision]", Depends(_get_assessor)]
