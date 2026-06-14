# Voico Calls Dashboard — developer tasks. Backend: uv. Frontend: npm.
.DEFAULT_GOAL := help
.PHONY: help up down logs test test-back test-front lint type fmt migrate seed openapi mutate

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up: ## Build and start the full stack (API :8000, UI :5173)
	docker compose up --build

down: ## Stop the stack and remove its volume
	docker compose down -v

logs: ## Follow container logs
	docker compose logs -f

test: test-back test-front ## Run all tests

test-back: ## Backend test suite
	uv --directory backend run pytest

test-front: ## Frontend test suite
	npm --prefix frontend run test

lint: ## Lint backend + frontend
	uv --directory backend run ruff check .
	npm --prefix frontend run lint

type: ## Type-check backend + frontend
	uv --directory backend run mypy app
	npm --prefix frontend run build

fmt: ## Format backend
	uv --directory backend run ruff format .

migrate: ## Apply DB migrations
	uv --directory backend run alembic upgrade head

seed: ## Seed sample data
	uv --directory backend run python scripts/seed.py

openapi: ## Regenerate docs/api/openapi.json
	uv --directory backend run python scripts/export_openapi.py

mutate: ## Mutation-test the calls module (slow; NOT a CI gate — see docs/ENGINEERING.md)
	uv --directory backend run mutmut run --paths-to-mutate app/modules/calls/ || true
	uv --directory backend run mutmut results
