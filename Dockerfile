ARG PYTHON_VERSION=3.12

# ── base: shared dependency install ───────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS base

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install directly into the system Python — no venv needed in containers
ENV UV_SYSTEM_PYTHON=1

WORKDIR /app

# Dependencies first for layer caching — source changes don't bust this layer
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-cache

COPY src/ ./src/
RUN uv pip install --no-deps -e . --no-cache-dir

# ── runtime ───────────────────────────────────────────────────────────────────
FROM base AS runtime

EXPOSE 8000

CMD ["uvicorn", "alias.app:app", "--host", "0.0.0.0", "--port", "8000"]

# ── test ──────────────────────────────────────────────────────────────────────
FROM base AS test

# Add dev deps (pytest, httpx, etc.)
RUN uv sync --frozen --no-cache

COPY tests/ ./tests/

CMD ["pytest", "tests/", "-v"]
