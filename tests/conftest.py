from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from alias.app import create_app
from alias.settings import Settings


@pytest.fixture
def test_settings() -> Settings:
    # _env_file=None disables .env file loading. OS-level ALIAS_* environment
    # variables are still read by BaseSettings — keep them unset in your local
    # shell to avoid polluting the test suite.
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
