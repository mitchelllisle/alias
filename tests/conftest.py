from collections.abc import AsyncGenerator, Generator
from concurrent.futures import ThreadPoolExecutor

import pytest
from httpx import ASGITransport, AsyncClient

from alias.app import create_app
from alias.engine.analyser import AsyncAnalyser, build_analyser_engine
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
    engine = build_analyser_engine(spacy_model=test_settings.spacy_model)
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
