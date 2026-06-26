from collections.abc import AsyncGenerator, Generator
from concurrent.futures import ThreadPoolExecutor

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic_ai import Agent

from alias.app import create_app
from alias.engine.analyser import AsyncAnalyser, build_analyser_engine
from alias.engine.anonymiser import AsyncAnonymiser
from alias.judge.service import JudgeDecision
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


@pytest.fixture
async def client(test_settings: Settings) -> AsyncGenerator[AsyncClient, None]:
    """Baseline client — no engine state injected. Use for health tests."""
    app = create_app(settings=test_settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def detect_client(test_settings: Settings, analyser: AsyncAnalyser) -> AsyncGenerator[AsyncClient, None]:
    """Client with analyser injected into app.state for detect endpoint tests."""
    app = create_app(settings=test_settings)
    app.state.analyser = analyser
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture(scope="session")
def anonymiser() -> Generator[AsyncAnonymiser, None, None]:
    """Build the AnonymizerEngine once per session."""
    from presidio_anonymizer import AnonymizerEngine
    executor = ThreadPoolExecutor(max_workers=2)
    yield AsyncAnonymiser(AnonymizerEngine(), executor)
    executor.shutdown(wait=True)


@pytest.fixture
async def anonymise_client(
    test_settings: Settings,
    analyser: AsyncAnalyser,
    anonymiser: AsyncAnonymiser,
) -> AsyncGenerator[AsyncClient, None]:
    """Client with both analyser and anonymiser injected for anonymise endpoint tests."""
    app = create_app(settings=test_settings)
    app.state.analyser = analyser
    app.state.anonymiser = anonymiser
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture(scope="session")
def judge_agent() -> Agent[None, JudgeDecision]:
    """TestModel-backed judge agent — deterministic, no real LLM calls."""
    from pydantic_ai.models.test import TestModel
    return Agent(TestModel(), output_type=JudgeDecision, system_prompt="test")


@pytest.fixture
async def judge_client(
    test_settings: Settings,
    analyser: AsyncAnalyser,
    anonymiser: AsyncAnonymiser,
    judge_agent: Agent[None, JudgeDecision],
) -> AsyncGenerator[AsyncClient, None]:
    """Client with analyser, anonymiser, and TestModel judge injected."""
    app = create_app(settings=test_settings)
    app.state.analyser = analyser
    app.state.anonymiser = anonymiser
    app.state.judge = judge_agent
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
