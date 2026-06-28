"""Fixtures for the MCP tool tests.

engine_state builds real engines (no mocks). The Context is a minimal
SimpleNamespace — just enough to satisfy _state(ctx); no MagicMock needed.
"""

from __future__ import annotations

from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from typing import Any

import pytest
from presidio_anonymizer import AnonymizerEngine

from priveil.engine.analyser import AsyncAnalyser, build_analyser_engine
from priveil.engine.pseudonymiser import AsyncPseudonymiser
from priveil.mcp.server import _State
from priveil.recognisers.registry import build_recognisers


@pytest.fixture(scope="session")
def engine_state() -> Generator[_State, None, None]:
    """Real analyser + pseudonymiser, no judge model.

    Session-scoped so spaCy loads once. Executor is shut down on teardown.
    """
    executor = ThreadPoolExecutor(max_workers=2)
    engine = build_analyser_engine(
        spacy_model="en_core_web_sm",
        extra_recognisers=build_recognisers(),
    )
    state = _State(
        analyser=AsyncAnalyser(engine, executor),
        pseudonymiser=AsyncPseudonymiser(AnonymizerEngine(), executor),  # type: ignore[no-untyped-call]
        refiner=None,
        assessor=None,
        executor=executor,
    )
    yield state
    executor.shutdown(wait=True)


def make_ctx(state: _State) -> Any:
    """Minimal context stand-in that satisfies _state(ctx)."""
    return SimpleNamespace(request_context=SimpleNamespace(lifespan_context=state))
