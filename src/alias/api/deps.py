from typing import Annotated, cast

from fastapi import Depends, Request

from alias.engine.analyser import AsyncAnalyser


def _get_analyser(request: Request) -> AsyncAnalyser:
    return cast(AsyncAnalyser, request.app.state.analyser)


AnalyserDep = Annotated[AsyncAnalyser, Depends(_get_analyser)]
