from collections.abc import AsyncGenerator, Generator
from concurrent.futures import ThreadPoolExecutor

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from alias.app import create_app
from alias.engine.analyser import AsyncAnalyser, build_analyser_engine
from alias.engine.pseudonymiser import AsyncPseudonymiser
from alias.judge.assessor import AssessmentDecision
from alias.judge.refiner import RefinerDecision
from alias.recognisers.registry import build_recognisers
from alias.settings import Settings


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    # _env_file=None disables .env file loading. OS-level ALIAS_* environment
    # variables are still read by BaseSettings — keep them unset in your local
    # shell to avoid polluting the test suite.
    return Settings(_env_file=None, spacy_model="en_core_web_sm")


@pytest.fixture(scope="session")
def analyser(test_settings: Settings) -> Generator[AsyncAnalyser, None, None]:
    """Build the analyser engine once per session — spaCy load is expensive."""
    executor = ThreadPoolExecutor(max_workers=2)
    engine = build_analyser_engine(
        spacy_model=test_settings.spacy_model,
        extra_recognisers=build_recognisers(),
    )
    yield AsyncAnalyser(engine, executor)
    executor.shutdown(wait=True)


@pytest.fixture(scope="session")
def pseudonymiser() -> Generator[AsyncPseudonymiser, None, None]:
    """Build the AnonymizerEngine once per session."""
    from presidio_anonymizer import AnonymizerEngine
    executor = ThreadPoolExecutor(max_workers=2)
    yield AsyncPseudonymiser(AnonymizerEngine(), executor)
    executor.shutdown(wait=True)


@pytest.fixture(scope="session")
def refiner_agent() -> Agent[None, RefinerDecision]:
    """TestModel-backed refiner — deterministic, no real LLM calls."""
    return Agent(TestModel(), output_type=RefinerDecision, system_prompt="test")


@pytest.fixture(scope="session")
def assessor_agent() -> Agent[None, AssessmentDecision]:
    """TestModel-backed assessor — deterministic, no real LLM calls."""
    return Agent(TestModel(), output_type=AssessmentDecision, system_prompt="test")


# ── Clients ───────────────────────────────────────────────────────────────────

@pytest.fixture
async def client(test_settings: Settings) -> AsyncGenerator[AsyncClient, None]:
    """Baseline client — no engine state injected. Use for health tests."""
    app = create_app(settings=test_settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def detect_client(test_settings: Settings, analyser: AsyncAnalyser) -> AsyncGenerator[AsyncClient, None]:
    """Analyser only — no refiner. Tests that refine=True is silently skipped."""
    app = create_app(settings=test_settings)
    app.state.analyser = analyser
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def pseudonymise_client(
    test_settings: Settings,
    analyser: AsyncAnalyser,
    pseudonymiser: AsyncPseudonymiser,
) -> AsyncGenerator[AsyncClient, None]:
    """Analyser + pseudonymiser, no refiner."""
    app = create_app(settings=test_settings)
    app.state.analyser = analyser
    app.state.pseudonymiser = pseudonymiser
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def refined_client(
    test_settings: Settings,
    analyser: AsyncAnalyser,
    pseudonymiser: AsyncPseudonymiser,
    refiner_agent: Agent[None, RefinerDecision],
) -> AsyncGenerator[AsyncClient, None]:
    """Analyser + pseudonymiser + TestModel refiner — tests the refine path."""
    app = create_app(settings=test_settings)
    app.state.analyser = analyser
    app.state.pseudonymiser = pseudonymiser
    app.state.refiner = refiner_agent
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def assess_client(
    test_settings: Settings,
    analyser: AsyncAnalyser,
    assessor_agent: Agent[None, AssessmentDecision],
) -> AsyncGenerator[AsyncClient, None]:
    """Analyser + TestModel assessor — for /assess endpoint tests."""
    app = create_app(settings=test_settings)
    app.state.analyser = analyser
    app.state.assessor = assessor_agent
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
