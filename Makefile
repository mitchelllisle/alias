.DEFAULT_GOAL := help

# Prefer Docker Compose v2 (`docker compose`), fall back to legacy v1 (`docker-compose`).
DOCKER_COMPOSE := $(shell if docker compose version >/dev/null 2>&1; then echo "docker compose"; elif command -v docker-compose >/dev/null 2>&1; then echo "docker-compose"; else echo "docker compose"; fi)

.PHONY: help install serve test lint format docker-build docker-serve docker-test

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies
	uv sync --all-groups

serve: ## Run the server locally with hot-reload
	uv run uvicorn alias.app:app --reload --host 0.0.0.0 --port 8000

test: ## Run tests locally
	uv run pytest tests/ -v

lint: ## Lint and type-check
	uv run ruff check src/ tests/
	uv run mypy src/

format: ## Auto-fix lint issues
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

docker-build: ## Build all Docker images
	$(DOCKER_COMPOSE) build

docker-serve: ## Run the service via Docker
	$(DOCKER_COMPOSE) up api

docker-test: ## Run tests via Docker
	$(DOCKER_COMPOSE) run --rm test
