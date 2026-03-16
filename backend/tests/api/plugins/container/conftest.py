"""Shared fixtures for container plugin tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_app():
    """Create mock app with options fixture."""
    mock_options = MagicMock()
    mock_options.code_reviewer.oauth_token = None
    mock_options.code_reviewer.anthropic_api_key = "test-anthropic-key"
    mock_options.code_reviewer.anthropic_base_url = None
    mock_options.code_reviewer.review_model = None
    mock_options.code_reviewer.utility_model = None

    app = MagicMock()
    app.options = mock_options

    # Mock GitHub plugin for installation token
    app.github = MagicMock()
    app.github.get_installation_access_token = AsyncMock(return_value="github-token-123")

    # Mock database plugin (None by default, set in specific tests)
    app.database = None

    return app


@pytest.fixture
def mock_broker():
    """Create mock Redis broker fixture."""
    broker = MagicMock()
    broker.publish = AsyncMock()
    return broker


@pytest.fixture
def mock_redis():
    """Create mock Redis client fixture."""
    redis = MagicMock()
    redis.sadd = AsyncMock(return_value=1)
    redis.srem = AsyncMock(return_value=1)
    redis.smembers = AsyncMock(return_value=set())
    redis.sismember = AsyncMock(return_value=False)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    return redis
