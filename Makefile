.DEFAULT_GOAL := help

.PHONY: help install install-docs serve test lint format docker-build docker-serve docker-test

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies
	uv sync --all-groups

install-docs: ## Install docs dependencies
	uv sync --group docs

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
	docker compose build

docker-serve: ## Run the service via Docker
	docker compose up api

docker-test: ## Run tests via Docker
	docker compose run --rm test
