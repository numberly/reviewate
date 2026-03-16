"""Tests for GitHub plugin installation token generation."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from api.plugins.github.config import GitHubAppConfig, GitHubPluginConfig
from api.plugins.github.plugin import GitHubPlugin


@pytest.mark.asyncio
async def test_generate_jwt_success(mock_github_app_private_key):
    """Test successful JWT generation."""
    # Create config with mock private key
    config = GitHubAppConfig(
        client_id="test-client-id",
        client_secret="test-client-secret",
        app_id="12345",
        private_key_path=str(mock_github_app_private_key),
        webhook_secret="test-webhook-secret",
        name="test-app",
    )
    plugin_config = GitHubPluginConfig(enabled=True, app=config)

    # Create plugin and load private key
    github = GitHubPlugin(plugin_config)
    github._private_key = mock_github_app_private_key.read_text()

    # Generate JWT
    jwt_token = github._generate_jwt()

    assert jwt_token is not None
    assert isinstance(jwt_token, str)
    assert len(jwt_token) > 0


@pytest.mark.asyncio
async def test_generate_jwt_no_private_key():
    """Test JWT generation fails without private key."""
    config = GitHubAppConfig(
        client_id="test-client-id",
        client_secret="test-client-secret",
        app_id="12345",
        private_key_path="/dev/null",
        webhook_secret="test-webhook-secret",
        name="test-app",
    )
    plugin_config = GitHubPluginConfig(enabled=True, app=config)

    github = GitHubPlugin(plugin_config)
    github._private_key = None

    with pytest.raises(HTTPException) as exc_info:
        github._generate_jwt()

    assert exc_info.value.status_code == 500
    assert "private key not loaded" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_installation_token_success(
    mock_github_app_private_key,
    mock_github_installation_token_response,
):
    """Test successful installation token retrieval."""
    config = GitHubAppConfig(
        client_id="test-client-id",
        client_secret="test-client-secret",
        app_id="12345",
        private_key_path=str(mock_github_app_private_key),
        webhook_secret="test-webhook-secret",
        name="test-app",
    )
    plugin_config = GitHubPluginConfig(enabled=True, app=config)

    # Create plugin and load private key
    github = GitHubPlugin(plugin_config)
    github._private_key = mock_github_app_private_key.read_text()

    # Mock HTTP response
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = mock_github_installation_token_response
    github.http.post = AsyncMock(return_value=mock_response)

    # Execute
    token = await github.get_installation_access_token("12345")

    assert token == "ghs_test_installation_token_1234567890"
    github.http.post.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_installation_repositories_success(mock_github_repositories_response):
    """Test fetching installation repositories."""
    config = GitHubAppConfig(
        client_id="test-client-id",
        client_secret="test-client-secret",
        app_id="12345",
        private_key_path="/dev/null",
        webhook_secret="test-webhook-secret",
        name="test-app",
    )
    plugin_config = GitHubPluginConfig(enabled=True, app=config)

    github = GitHubPlugin(plugin_config)

    # Mock HTTP response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_github_repositories_response
    github.http.get = AsyncMock(return_value=mock_response)

    # Execute
    repos = await github.fetch_installation_repositories("test_token")

    assert len(repos) == 2
    assert repos[0]["name"] == "test-repo-1"
    github.http.get.assert_called_once()


@pytest.mark.asyncio
async def test_get_installation_token_api_error(mock_github_app_private_key):
    """Test installation token retrieval handles API errors."""
    config = GitHubAppConfig(
        client_id="test-client-id",
        client_secret="test-client-secret",
        app_id="12345",
        private_key_path=str(mock_github_app_private_key),
        webhook_secret="test-webhook-secret",
        name="test-app",
    )
    plugin_config = GitHubPluginConfig(enabled=True, app=config)

    github = GitHubPlugin(plugin_config)
    github._private_key = mock_github_app_private_key.read_text()

    # Mock failed HTTP response
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Installation not found"
    github.http.post = AsyncMock(return_value=mock_response)

    # Execute and expect error
    with pytest.raises(HTTPException) as exc_info:
        await github.get_installation_access_token("99999")

    assert exc_info.value.status_code == 404
    assert "GitHub API error" in exc_info.value.detail
