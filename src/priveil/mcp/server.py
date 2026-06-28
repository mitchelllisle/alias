"""FastMCP server and lifespan for priveil.

This module is part of the optional ``mcp`` extra::

    pip install "priveil[mcp]"
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import cast

from presidio_anonymizer import AnonymizerEngine
from pydantic_ai import Agent

from priveil.engine.analyser import AsyncAnalyser, build_analyser_engine
from priveil.engine.pseudonymiser import AsyncPseudonymiser
from priveil.judge.assessor import AssessmentDecision
from priveil.judge.refiner import RefinerDecision
from priveil.recognisers.registry import build_recognisers
from priveil.settings import Settings

try:
    from mcp.server.fastmcp import Context, FastMCP
except ImportError as exc:
    raise ImportError(
        'The priveil MCP server requires the optional "mcp" extra. '
        'Install it with: pip install "priveil[mcp]"'
    ) from exc


@dataclass
class _State:
    analyser: AsyncAnalyser
    pseudonymiser: AsyncPseudonymiser
    refiner: Agent[None, RefinerDecision] | None
    assessor: Agent[None, AssessmentDecision] | None
    executor: ThreadPoolExecutor


def _require_spacy_model(model_name: str) -> None:
    """Fail fast if the spaCy model is not installed.

    The MCP server runs as a subprocess and must be ready immediately.
    Blocking to download a model during the MCP handshake causes clients
    to time out. Raise with a clear install command instead.

    Args:
        model_name: spaCy model name, e.g. 'en_core_web_sm'.

    Raises:
        SystemExit: If the model is not found, with an install hint.
    """
    import importlib.util
    if importlib.util.find_spec(model_name.replace("-", "_")) is None:
        raise SystemExit(
            f"spaCy model '{model_name}' is not installed.\n"
            f"Run: python -m spacy download {model_name}"
        )


@asynccontextmanager
async def _lifespan(server: FastMCP) -> AsyncIterator[_State]:
    settings = Settings()
    _require_spacy_model(settings.spacy_model)
    executor = ThreadPoolExecutor(max_workers=settings.executor_max_workers)
    engine = build_analyser_engine(
        spacy_model=settings.spacy_model,
        extra_recognisers=build_recognisers(),
    )
    refiner: Agent[None, RefinerDecision] | None = None
    assessor: Agent[None, AssessmentDecision] | None = None
    if settings.judge_model or settings.judge_base_url:
        from priveil.judge.assessor import build_assessor_agent
        from priveil.judge.refiner import build_refiner_agent

        refiner = build_refiner_agent(settings)
        assessor = build_assessor_agent(settings)

    state = _State(
        analyser=AsyncAnalyser(engine, executor),
        pseudonymiser=AsyncPseudonymiser(AnonymizerEngine(), executor),  # type: ignore[no-untyped-call]  # conduit: presidio untyped
        refiner=refiner,
        assessor=assessor,
        executor=executor,
    )
    try:
        yield state
    finally:
        executor.shutdown(wait=True)


mcp = FastMCP("priveil", lifespan=_lifespan)


def get_state(ctx: Context) -> _State:  # type: ignore[type-arg]  # conduit: FastMCP Context not generic at runtime
    """Extract typed engine state from the FastMCP request context.

    Args:
        ctx: The FastMCP request context, injected by the framework.

    Returns:
        The _State instance yielded by _lifespan.
    """
    # FastMCP types lifespan_context as object; cast is safe — _lifespan yields _State.
    return cast(_State, ctx.request_context.lifespan_context)


def main() -> None:
    """Run the priveil MCP server over stdio."""
    import priveil.mcp.tools  # noqa: F401 — triggers @mcp.tool() registration

    mcp.run()
