# Daily commands of the project. Run `just` to list them.

set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]
set dotenv-load

backend_port := env("BACKEND_PORT", "8010")
frontend_port := env("FRONTEND_PORT", "3010")

# List the available commands
default:
    @just --list

# Install Python and Node dependencies and the git hooks
setup:
    uv sync
    pnpm --dir frontend install
    uv run pre-commit install

# Start only Postgres in Docker (daily development)
db:
    docker compose up -d --wait postgres

# Backend with auto reload on http://127.0.0.1:8010
backend:
    uv run uvicorn app.main:create_app --factory --reload --reload-dir backend/src --port {{backend_port}}

# Frontend with hot reload on http://localhost:3010
frontend:
    pnpm --dir frontend dev --port {{frontend_port}}

# Whole stack in containers, as it would run in production
up:
    docker compose --profile app up -d --build --wait

# Stop every container of the project (data volumes are kept)
down:
    docker compose --profile app down

# Follow container logs, e.g. `just logs backend`
logs service="":
    docker compose --profile app logs -f {{service}}

# Linters for backend and frontend
lint:
    uv run ruff check .
    uv run ruff format --check .
    pnpm --dir frontend exec biome ci

# Auto-fix lint and formatting issues
fmt:
    uv run ruff check --fix .
    uv run ruff format .
    pnpm --dir frontend exec biome check --write

# Static type checks
typecheck:
    uv run mypy
    pnpm --dir frontend typecheck

# Unit tests
test:
    uv run pytest
    pnpm --dir frontend test

# Everything CI checks, except the Docker smoke test
check: lint typecheck test

# Regenerate the OpenAPI schema and the typed frontend client
gen-api:
    uv run python -m app.scripts.export_openapi frontend/openapi.json
    pnpm --dir frontend gen:api

# Run all git hooks on every file
hooks:
    uv run pre-commit run --all-files
