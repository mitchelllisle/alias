ARG PYTHON_VERSION=3.12

# ── base: production dependency install ───────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS base

COPY --from=ghcr.io/astral-sh/uv:0.11.24 /uv /usr/local/bin/uv

ENV UV_SYSTEM_PYTHON=1

WORKDIR /app

# Dependencies before source for layer caching
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-cache

COPY src/ ./src/
RUN uv pip install --no-deps . --no-cache-dir

# ── runtime ───────────────────────────────────────────────────────────────────
FROM base AS runtime

# Production deployments use en_core_web_lg; download at deploy time via:
#   ALIAS_SPACY_MODEL=en_core_web_lg python -m spacy download en_core_web_lg
# or bake into a derived image.
EXPOSE 8000

CMD ["uv", "run", "uvicorn", "alias.app:app", "--host", "0.0.0.0", "--port", "8000"]

# ── test ──────────────────────────────────────────────────────────────────────
FROM base AS test

# Dev deps include en-core-web-sm (pinned in pyproject.toml dependency-groups.dev)
# so the model is always installed by uv sync — no fragile download step needed.
RUN uv sync --frozen --no-cache

COPY tests/ ./tests/

CMD ["uv", "run", "pytest", "tests/", "-v"]
