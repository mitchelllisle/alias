from typing import Annotated, cast

from fastapi import Depends, HTTPException, Request
from pydantic_ai import Agent

from priveil.engine.analyser import AsyncAnalyser
from priveil.engine.pseudonymiser import AsyncPseudonymiser
from priveil.judge.assessor import AssessmentDecision
from priveil.judge.refiner import Refiner


def _get_analyser(request: Request) -> AsyncAnalyser:
    return cast(AsyncAnalyser, request.app.state.analyser)


AnalyserDep = Annotated[AsyncAnalyser, Depends(_get_analyser)]

def _get_pseudonymiser(request: Request) -> AsyncPseudonymiser:
    return cast(AsyncPseudonymiser, request.app.state.pseudonymiser)


PseudonymiserDep = Annotated[AsyncPseudonymiser, Depends(_get_pseudonymiser)]


def _get_refiner(request: Request) -> Refiner | None:
    return request.app.state.refiner  # type: ignore[no-any-return]  # conduit: app.state is untyped by FastAPI


# Optional — routes fall back to fast mode (with surfaced mode_used) when this is None.
RefinerDep = Annotated[Refiner | None, Depends(_get_refiner)]


def _get_assessor(request: Request) -> "Agent[None, AssessmentDecision]":
    agent = request.app.state.assessor
    if agent is None:
        raise HTTPException(
            status_code=503,
            detail="Assessment not available — set PRIVEIL_JUDGE_MODEL to enable",
        )
    return agent  # type: ignore[no-any-return]  # conduit: app.state is untyped by FastAPI


AssessorDep = Annotated["Agent[None, AssessmentDecision]", Depends(_get_assessor)]
