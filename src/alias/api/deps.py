from typing import Annotated, cast

from fastapi import Depends, Request

from alias.engine.analyser import AsyncAnalyser
from alias.engine.anonymiser import AsyncAnonymiser


def _get_analyser(request: Request) -> AsyncAnalyser:
    return cast(AsyncAnalyser, request.app.state.analyser)


AnalyserDep = Annotated[AsyncAnalyser, Depends(_get_analyser)]

def _get_anonymiser(request: Request) -> AsyncAnonymiser:
    return cast(AsyncAnonymiser, request.app.state.anonymiser)


AnonymiserDep = Annotated[AsyncAnonymiser, Depends(_get_anonymiser)]
