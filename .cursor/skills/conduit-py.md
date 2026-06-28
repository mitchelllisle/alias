---
name: conduit-py
description: >
  Python tooling for the conduit discipline — Pydantic at every serialisation
  boundary, pure composable functions, Google-style docstrings, and a
  pytest + hypothesis test stack. Tailored for priveil: a FastAPI
  pseudonymisation service backed by presidio, spaCy, and pydantic-ai.
  Read conduit-core for the ladder, philosophy, and security principles.
argument-hint: "[lite|full|ultra]"
---

> Read `conduit-core` before this file. This skill adds Python-specific tooling
> and priveil-specific conventions.

# Conduit — Python (priveil)

## Data & Types

- Pydantic models at every serialisation boundary: HTTP request/response,
  env vars (`BaseSettings`), LLM structured output, MCP tool returns.
- Domain models are **frozen** (`BaseModel, frozen=True`). Mutate by
  constructing a new instance, never by patching fields.
- `OperatorType`, `Sensitivity`, `mode` are `Literal` aliases — not enums,
  not plain strings. Use `cast(OperatorType, v)` with an explicit runtime
  guard when accepting from external input.
- Never reach into deserialized JSON with `.get()` chains when a model exists.
  Use `Model.model_validate(data)`.
- Type hints on every function signature, return type included.
- `# type: ignore[code]` requires a trailing comment: `# conduit: [reason]`.
  Never use bare `# type: ignore`.
- Never use `Any` without `# conduit: Any here because [reason]`.

## FastAPI Conventions

- Routes are **thin wrappers** — one `await` call, return the result.
  No business logic in route functions.
- Engine state (analyser, pseudonymiser, refiner, assessor) lives on
  `app.state`, initialised in the lifespan and injected via `deps.py`.
- CPU-bound presidio/spaCy work is always offloaded to a `ThreadPoolExecutor`
  via `asyncio.get_event_loop().run_in_executor`. Never block the event loop.
- Lifespan owns resource lifecycle (executors, model loading). Routes never
  construct engines.
- HTTP errors are raised via `HTTPException`; domain errors (bad input) are
  Pydantic `ValidationError` surfaced automatically by FastAPI.
- Every response model is a frozen Pydantic model. No raw dicts on the API
  surface.

## Mode and Degradation

- `mode: Literal["fast", "judge"]` is the canonical switch for LLM involvement.
  `"judge"` silently no-ops to `"fast"` when no judge model is configured —
  **never raise** on an unconfigured judge in the detection or anonymisation
  path. Only `/assess` raises (503) because it has no fast fallback.
- New LLM-backed features follow the same pattern: degrade gracefully when the
  model is unset, document the no-op in the docstring.

## Async & Concurrency

- `async def` everywhere in routes, engine wrappers, and MCP tools.
- CPU-bound calls (presidio analyse/anonymise, spaCy) go through the shared
  `ThreadPoolExecutor` on `app.state`. Never `await` them directly.
- Session-scoped pytest fixtures for expensive resources (spaCy model load,
  executor). Yield fixtures with explicit `executor.shutdown(wait=True)` teardown.

## Security Champion (Python surface)

- No secrets in logs, no secrets in code. All config via `BaseSettings` with
  `PRIVEIL_` prefix.
- `judge_api_key` and any bearer token **must** be `SecretStr`, never `str`.
  Access the raw value only at the point of use: `.get_secret_value()`.
- All external input is hostile until Pydantic has validated it. Trust boundary
  = the Pydantic model constructor. After that, trust the type.
- The `entity_map` from pseudonymisation contains original PII. Treat it as
  sensitive in documentation, error messages, and log guidance.
- On bad input: Pydantic raises `ValidationError` automatically. For domain
  errors (invalid operator, unconfigured judge): raise `ValueError` with a
  clear message that names the env var to set.

## Documentation

- Google-style docstrings on every non-trivial function.
- One-line imperative summary (`Detect PII entities…`, `Build the assessor…`).
- Args / Returns / Raises — one short line each, only what the type doesn't say.
- For mode-dependent behaviour, document the degradation path explicitly.
- Never document what the type signature already says.

## Test Stack

- `pytest` for all test running. No `unittest`.
- `asyncio_mode = "auto"` in pytest config; use `async def test_` directly.
- Three test layers — keep them separate:
  - `tests/unit/` — pure function tests. No engines, no network. Fast.
  - `tests/integration/` — full HTTP request→response via `httpx.AsyncClient`.
    Uses `TestModel` (pydantic-ai) for LLM-backed paths.
  - `tests/mcp/` — MCP tool tests. Real engines, `SimpleNamespace` context
    stand-in. No MagicMock.
- No mocks of internal logic — test real behaviour with real (small) data.
  `TestModel` is the one exception: use it for pydantic-ai agent paths to
  avoid real LLM calls in CI.
- `hypothesis` for data edge cases on pure functions: recogniser checksums,
  entity map construction, operator override merging. Annotate strategy choices.
- Session-scoped fixtures for spaCy model and engine construction. Function-
  scoped for HTTP clients (each test gets a clean app state).

## Presidio / spaCy Notes

- `AnonymizerEngine()` and `AnalyzerEngine` constructors are untyped (presidio
  ships no stubs). Annotate ignores: `# type: ignore[no-untyped-call]  # conduit: presidio untyped`.
- AU-specific recognisers live in `recognisers/`. Each recogniser owns exactly
  one `EntityType`. Checksum validation is mandatory for AU_TFN, AU_ABN,
  AU_MEDICARE, AU_ACN — the issuing authority publishes the algorithm.
- `EntityType` is a `str`-`Enum`. `ENTITY_CLASSIFICATION` must have an entry
  for every member — a missing key is a bug, not a default.
