# Reviewate Backend

FastAPI backend with a plugin-based architecture for the Reviewate platform.

## Tech Stack

- **FastAPI** — Web framework
- **SQLAlchemy** + **Alembic** — ORM and migrations
- **FastStream** — Redis message broker for async job dispatch
- **PostgreSQL** — Primary database
- **Redis** — Queue backend and execution tracking

## Architecture

The backend uses a **plugin system** where each feature is encapsulated in a plugin:

- `DatabasePlugin` — SQLAlchemy database connections
- `GitHubPlugin` / `GitLabPlugin` — OAuth and API clients
- `WebServerPlugin` — FastAPI routes and uvicorn server
- `FastStreamPlugin` — Redis message broker for async jobs

The `Application` class in `api/app.py` is the central container. It loads plugins based on YAML config and manages their lifecycle (startup/shutdown).

## Development Setup

```bash
# Start database and run migrations (from monorepo root)
make compose-test

# Start the dev server
make backend-run  # http://localhost:8000
```

### Configuration

Config is loaded from YAML files in `configs/` (e.g., `docker.yaml`). Environment variables override YAML values. See [docs/environment-variables.md](../docs/environment-variables.md) for the full reference.

Copy the example env file to get started:

```bash
cp .env.example .env
```

## Testing

```bash
# Run backend tests
make backend-test

# Or directly with pytest
cd backend && uv run pytest
```

Tests use pytest with fixtures from `tests/conftest.py`.

## Code Style

- Formatted and linted with [Ruff](https://docs.astral.sh/ruff/)
- Type hints required on all public functions
- Docstrings on public classes and methods

```bash
# Run linting and formatting checks
make qa
```
