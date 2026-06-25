from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from alias.app import create_app
from alias.settings import Settings


@pytest.fixture
def test_settings() -> Settings:
    # Construct with explicit values and disable .env loading so the test
    # suite is hermetic — local .env files or environment variables cannot
    # leak in and change behaviour.
    return Settings(_env_file=None)


@pytest.fixture
async def client(test_settings: Settings) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient wired to the app.

    ASGITransport does not trigger the ASGI lifespan scope. State is injected
    directly in each fixture that needs it.
    """
    app = create_app(settings=test_settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
