import importlib.metadata
import logging
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from presidio_anonymizer import AnonymizerEngine

from priveil.api.routes import assess, detect, health, pseudonymise
from priveil.domain.detection import DetectionRequest
from priveil.engine.analyser import AsyncAnalyser, build_analyser_engine
from priveil.engine.pseudonymiser import AsyncPseudonymiser
from priveil.recognisers.registry import build_recognisers
from priveil.settings import Settings

logger = logging.getLogger(__name__)


def _version() -> str:
    """Return the package version, falling back to 'dev' for source checkouts."""
    try:
        return importlib.metadata.version("priveil")
    except importlib.metadata.PackageNotFoundError:
        return "dev"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown hook — initialise engines, yield, then clean up."""
    settings: Settings = app.state.settings
    executor = ThreadPoolExecutor(max_workers=settings.executor_max_workers)
    engine = build_analyser_engine(
        spacy_model=settings.spacy_model,
        extra_recognisers=build_recognisers(),
    )
    audit_hash_key = settings.audit_hash_key.get_secret_value().encode() if settings.audit_hash_key else None
    if audit_hash_key is None:
        logger.warning(
            "PRIVEIL_AUDIT_HASH_KEY is unset; using an ephemeral process-local audit hash key. "
            "Set PRIVEIL_AUDIT_HASH_KEY to keep hashes stable across restarts."
        )
    app.state.analyser = AsyncAnalyser(engine, executor, audit_hash_key=audit_hash_key)
    app.state.pseudonymiser = AsyncPseudonymiser(AnonymizerEngine(), executor)  # type: ignore[no-untyped-call]  # conduit: presidio untyped

    if settings.judge_model or settings.judge_base_url:
        from priveil.judge.assessor import build_assessor_agent
        from priveil.judge.refiner import build_refiner

        app.state.refiner = build_refiner(settings)
        app.state.assessor = build_assessor_agent(settings)
    else:
        app.state.refiner = None
        app.state.assessor = None

    await app.state.analyser.analyse(DetectionRequest(text="Warmup: Jane Smith, TFN 123 456 782", mode="fast"))
    if app.state.refiner is not None:
        with suppress(Exception):
            warmup = await app.state.analyser.analyse(DetectionRequest(text="Warmup Jane Smith", mode="fast"))
            await app.state.refiner.refine("Warmup Jane Smith", warmup.entities)

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
        title="Priveil",
        description="Pseudonymisation service for reducing PII exposure in text workflows.",
        version=_version(),
        lifespan=lifespan,
    )
    app.state.settings = settings
    # Initialise all engine state to None so tests that bypass the lifespan
    # never hit AttributeError on app.state.<key>.
    app.state.analyser = None
    app.state.pseudonymiser = None
    app.state.refiner = None
    app.state.assessor = None

    app.include_router(health.router)
    app.include_router(detect.router, prefix="/detect", tags=["detection"])
    app.include_router(pseudonymise.router, prefix="/pseudonymise", tags=["pseudonymisation"])
    app.include_router(assess.router, prefix="/assess", tags=["assessment"])

    return app


app = create_app()
