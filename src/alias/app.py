from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI
from presidio_anonymizer import AnonymizerEngine

from alias.api.routes import anonymise, assess, detect, health
from alias.engine.analyser import AsyncAnalyser, build_analyser_engine
from alias.engine.anonymiser import AsyncAnonymiser
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
    app.state.anonymiser = AsyncAnonymiser(AnonymizerEngine(), executor)  # type: ignore[no-untyped-call]

    if settings.judge_model:
        from alias.judge.assessor import build_assessor_agent
        from alias.judge.refiner import build_refiner_agent

        app.state.refiner = build_refiner_agent(settings.judge_model, settings.judge_temperature)
        app.state.assessor = build_assessor_agent(settings.judge_model, settings.judge_temperature)
    else:
        app.state.refiner = None
        app.state.assessor = None

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
    # Initialise all engine state to None so tests that bypass the lifespan
    # never hit AttributeError on app.state.<key>.
    app.state.analyser = None
    app.state.anonymiser = None
    app.state.refiner = None
    app.state.assessor = None

    app.include_router(health.router)
    app.include_router(detect.router, prefix="/detect", tags=["detection"])
    app.include_router(anonymise.router, prefix="/anonymise", tags=["anonymisation"])
    app.include_router(assess.router, prefix="/assess", tags=["assessment"])

    return app


app = create_app()
