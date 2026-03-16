# Backend

FastAPI backend with plugin-based architecture.

## Architecture

The backend uses a **plugin system** where each feature is encapsulated in a plugin:

- `DatabasePlugin` - SQLAlchemy database connections
- `GitHubPlugin` / `GitLabPlugin` - OAuth and API clients
- `WebServerPlugin` - FastAPI routes and uvicorn server
- `FastStreamPlugin` - Redis message broker for async jobs

The `Application` class in `api/app.py` is the central container. It loads plugins based on YAML config and manages their lifecycle (startup/shutdown).

## Configuration

Config is loaded from YAML files in `configs/` (e.g., `local.yaml`). Environment variables override YAML values. The `BackendConfig` class in `config.py` validates and merges config sources.

## Consumers

FastStream consumers in `routers/*/consumer.py` subscribe to Redis channels and process async jobs. They use `@router.subscriber("channel.name")` decorator.

## Testing

Tests use pytest with fixtures from `tests/conftest.py`. Mock external dependencies with `@patch`:

```python
from unittest.mock import AsyncMock, MagicMock, patch

@patch("api.routers.webhooks.github.handlers.verify_github_signature")
@patch("api.routers.webhooks.github.handlers.get_faststream_broker")
def test_webhook(mock_broker, mock_verify, client, db_session):
    mock_broker.return_value.publish = AsyncMock()
    mock_verify.return_value = None
    # ... test code
```

Use `authenticated_client` fixture for auth-required endpoints. Use `db_session` for database access.

## Guidelines

- import should always be on top of the file
- follow existing code style and patterns
- write docstrings for public classes/functions
- add type hints for function signatures
