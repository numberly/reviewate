"""FastAPI app and client fixtures for testing."""

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.app import Application
from api.context import clear_current_app, set_current_app
from api.database import get_session
from api.plugins.faststream import get_faststream_broker
from api.routers.webhooks.github.dependencies import verify_github_webhook
from config import BackendConfig

TEST_CONFIG_PATH = Path(__file__).parent.parent / "static" / "test_config.yaml"


@pytest.fixture(scope="session")
def test_config() -> BackendConfig:
    """Load test configuration from static YAML file.

    Returns:
        BackendConfig: Test configuration instance
    """
    # Load from tests/static/test_config.yaml
    return BackendConfig.from_yaml_file(TEST_CONFIG_PATH)


@pytest.fixture(scope="function")
async def test_app(db_session: Session, test_config: BackendConfig):
    """Create a plugin-based test app with test database.

    This fixture creates the new Application instance, starts all plugins,
    and overrides the get_session dependency to use the test database.

    Args:
        db_session: Test database session fixture
        test_config: Test configuration fixture

    Yields:
        Application: Test application instance with FastAPI app in web plugin
    """
    # Create plugin-based application
    app = Application(test_config)
    # Register and start all plugins
    await app.register_plugins()

    # Get web plugin and override database dependency
    web_plugin = app.web
    if not web_plugin:
        raise RuntimeError("Web plugin not started")

    def override_get_session() -> Generator[Session]:
        try:
            yield db_session
        finally:
            pass

    web_plugin.app.dependency_overrides[get_session] = override_get_session

    # Also patch app.database.session() so code using `with app.database.session() as db:`
    # gets the same test session (not a separate connection/transaction)
    original_session = app.database.session

    @contextmanager
    def override_database_session() -> Generator[Session]:
        yield db_session

    app.database.session = override_database_session

    # Override FastStream broker dependency (disabled in tests)
    mock_broker = MagicMock()
    mock_broker.publish = AsyncMock()
    web_plugin.app.dependency_overrides[get_faststream_broker] = lambda: mock_broker

    # Override GitHub webhook verification (skip HMAC in tests)
    web_plugin.app.dependency_overrides[verify_github_webhook] = lambda: None

    # Manually register app in global context for testing
    set_current_app(app)

    yield app

    # Clean up
    app.database.session = original_session
    web_plugin.app.dependency_overrides.clear()
    await app.shutdown()
    clear_current_app()


@pytest.fixture(scope="function")
def client(test_app: Application) -> TestClient:
    """Create a test client for the FastAPI app.

    Args:
        test_app: Test application instance

    Returns:
        TestClient: FastAPI test client
    """
    web_plugin = test_app.web
    if not web_plugin or not web_plugin.app:
        raise RuntimeError("Web plugin not available")
    return TestClient(web_plugin.app)


@pytest.fixture(scope="function")
def authenticated_client(client: TestClient, create_user, jwt_token: str) -> TestClient:
    """Create an authenticated test client with a valid JWT token.

    Args:
        client: Base test client
        create_user: Test user fixture
        jwt_token: JWT token for the test user

    Returns:
        TestClient: Authenticated test client with session cookie set
    """
    client.cookies.set("reviewate_session", jwt_token)
    return client
