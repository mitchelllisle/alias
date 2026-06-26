from typing import Annotated, cast

from fastapi import Depends, HTTPException, Request
from pydantic_ai import Agent

from alias.engine.analyser import AsyncAnalyser
from alias.engine.anonymiser import AsyncAnonymiser
from alias.judge.service import JudgeDecision


def _get_analyser(request: Request) -> AsyncAnalyser:
    return cast(AsyncAnalyser, request.app.state.analyser)


AnalyserDep = Annotated[AsyncAnalyser, Depends(_get_analyser)]

def _get_anonymiser(request: Request) -> AsyncAnonymiser:
    return cast(AsyncAnonymiser, request.app.state.anonymiser)


AnonymiserDep = Annotated[AsyncAnonymiser, Depends(_get_anonymiser)]


def _get_judge(request: Request) -> Agent[None, JudgeDecision]:
    agent: Agent[None, JudgeDecision] | None = request.app.state.judge
    if agent is None:
        raise HTTPException(status_code=503, detail="LLM judge not configured — set ALIAS_JUDGE_MODEL")
    return agent


JudgeDep = Annotated[Agent[None, JudgeDecision], Depends(_get_judge)]
