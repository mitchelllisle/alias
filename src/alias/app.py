from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI

from alias.api.routes import detect, health
from alias.engine.analyser import AsyncAnalyser, build_analyser_engine
from alias.recognisers.registry import build_recognisers
from alias.settings import Settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown hook — initialise engines, yield, then clean up."""
    settings: Settings = app.state.settings
    executor = ThreadPoolExecutor(max_workers=settings.executor_max_workers)
    engine = build_analyser_engine(
        spacy_model=settings.spacy_model,
        extra_recognisers=build_recognisers(),
    )
    app.state.analyser = AsyncAnalyser(engine, executor)
    yield
    executor.shutdown(wait=True)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and return the configured FastAPI application.

    Args:
        settings: Optional override; defaults to env-driven Settings().

    Returns:
        A fully configured FastAPI app.
    """
    if settings is None:
        settings = Settings()

    app = FastAPI(
        title="Alias",
        description="Pseudonymisation service for Australian financial context",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.include_router(health.router)
    app.include_router(detect.router, prefix="/detect", tags=["detection"])

    return app


app = create_app()
