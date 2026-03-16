"""Service-related test fixtures for mocking OAuth and httpx clients."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# Constants for test config path
TEST_CONFIG_PATH = str(Path(__file__).parent.parent / "static" / "test_config.yaml")


@pytest.fixture
def mock_httpx_response():
    """Create a mock httpx response with success status."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}
    return mock_response


@pytest.fixture
def mock_httpx_error_response():
    """Create a mock httpx response with error status."""
    mock_response = Mock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"
    return mock_response


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx AsyncClient."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock()
    mock_client.post = AsyncMock()
    mock_client.aclose = AsyncMock()
    return mock_client


@pytest.fixture
def mock_oauth_client():
    """Create a mock OAuth client for Authlib."""
    mock_client = AsyncMock()
    mock_client.authorize_access_token = AsyncMock(
        return_value={
            "access_token": "test_token",
            "token_type": "bearer",
            "scope": "read:user",
        }
    )
    return mock_client


@pytest.fixture
def mock_github_user_response():
    """Create a mock GitHub user API response."""
    return {
        "id": 12345,
        "login": "githubuser",
        "email": "github@example.com",
        "name": "GitHub User",
        "avatar_url": "https://avatars.githubusercontent.com/u/12345",
        "html_url": "https://github.com/githubuser",
    }


@pytest.fixture
def mock_github_user_private_email():
    """Create a mock GitHub user API response with private email."""
    return {
        "id": 12345,
        "login": "privateuser",
        "email": None,  # Private email
        "name": "Private User",
        "avatar_url": "https://avatars.githubusercontent.com/u/12345",
        "html_url": "https://github.com/privateuser",
    }


@pytest.fixture
def mock_gitlab_user_response():
    """Create a mock GitLab user API response."""
    return {
        "id": 67890,
        "username": "gitlabuser",
        "email": "gitlab@example.com",
        "name": "GitLab User",
        "avatar_url": "https://gitlab.com/uploads/-/system/user/avatar/67890/avatar.png",
        "web_url": "https://gitlab.com/gitlabuser",
    }


@pytest.fixture
def mock_google_user_response():
    """Create a mock Google user API response."""
    return {
        "sub": "google-user-id-123",
        "email": "google@example.com",
        "email_verified": True,
        "name": "Google User",
        "given_name": "Google",
        "family_name": "User",
        "picture": "https://lh3.googleusercontent.com/a/default-user",
    }


@pytest.fixture
def setup_github_mocks(
    mock_oauth_client, mock_httpx_client, mock_github_user_response, mock_httpx_response
):
    """Set up all GitHub OAuth mocks with default successful response.

    Returns a tuple of (oauth_client, httpx_client) configured for GitHub auth flow.
    """
    # Configure httpx response
    mock_httpx_response.json.return_value = mock_github_user_response
    mock_httpx_client.get.return_value = mock_httpx_response

    return mock_oauth_client, mock_httpx_client


@pytest.fixture
def setup_gitlab_mocks(
    mock_oauth_client, mock_httpx_client, mock_gitlab_user_response, mock_httpx_response
):
    """Set up all GitLab OAuth mocks with default successful response.

    Returns a tuple of (oauth_client, httpx_client) configured for GitLab auth flow.
    """
    # Configure httpx response
    mock_httpx_response.json.return_value = mock_gitlab_user_response
    mock_httpx_client.get.return_value = mock_httpx_response

    return mock_oauth_client, mock_httpx_client


@pytest.fixture
def setup_google_mocks(
    mock_oauth_client, mock_httpx_client, mock_google_user_response, mock_httpx_response
):
    """Set up all Google OAuth mocks with default successful response.

    Returns a tuple of (oauth_client, httpx_client) configured for Google auth flow.
    """
    # Configure httpx response
    mock_httpx_response.json.return_value = mock_google_user_response
    mock_httpx_client.get.return_value = mock_httpx_response

    return mock_oauth_client, mock_httpx_client


@pytest.fixture
def mock_github_app_private_key(tmp_path):
    """Create a mock GitHub App RSA private key for testing.

    Returns:
        Path to temporary private key file
    """
    # Generate a 2048-bit RSA private key
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )

    # Serialize to PEM format
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # Write to temporary file
    private_key_file = tmp_path / "test_github_app_key.pem"
    private_key_file.write_bytes(pem)
    return private_key_file


@pytest.fixture
def mock_github_installation_token_response():
    """Create a mock GitHub installation access token response."""
    return {
        "token": "ghs_test_installation_token_1234567890",
        "expires_at": "2025-11-01T12:00:00Z",
        "permissions": {
            "contents": "read",
            "metadata": "read",
            "pull_requests": "write",
        },
        "repository_selection": "all",
    }


@pytest.fixture
def mock_github_repositories_response():
    """Create a mock GitHub installation repositories response."""
    return {
        "total_count": 2,
        "repositories": [
            {
                "id": 123456,
                "name": "test-repo-1",
                "full_name": "test-org/test-repo-1",
                "html_url": "https://github.com/test-org/test-repo-1",
                "private": False,
            },
            {
                "id": 789012,
                "name": "test-repo-2",
                "full_name": "test-org/test-repo-2",
                "html_url": "https://github.com/test-org/test-repo-2",
                "private": True,
            },
        ],
    }


@pytest.fixture
def mock_github_organizations_response():
    """Create a mock GitHub user organizations response."""
    return [
        {
            "id": 100001,
            "login": "test-org-1",
            "url": "https://api.github.com/orgs/test-org-1",
            "avatar_url": "https://avatars.githubusercontent.com/u/100001",
        },
        {
            "id": 100002,
            "login": "test-org-2",
            "url": "https://api.github.com/orgs/test-org-2",
            "avatar_url": "https://avatars.githubusercontent.com/u/100002",
        },
    ]


@pytest.fixture
def mock_github_installations_response():
    """Create a mock GitHub user installations response."""
    return {
        "total_count": 1,
        "installations": [
            {
                "id": 54321,
                "account": {
                    "id": 100003,
                    "login": "test-org-3",
                    "type": "Organization",
                },
                "app_id": 12345,
            }
        ],
    }


@pytest.fixture
def mock_gitlab_groups_response():
    """Create a mock GitLab user groups response."""
    return [
        {
            "id": 200001,
            "name": "Test Group 1",
            "path": "test-group-1",
            "web_url": "https://gitlab.com/groups/test-group-1",
        },
        {
            "id": 200002,
            "name": "Test Group 2",
            "path": "test-group-2",
            "web_url": "https://gitlab.com/groups/test-group-2",
        },
    ]


@pytest.fixture
def mock_github_oauth_token(mock_github_user_response):
    """Create a mock GitHub OAuth token with userinfo."""
    return {
        "access_token": "test_github_token",
        "token_type": "bearer",
        "scope": "read:user user:email",
        "userinfo": mock_github_user_response,
    }


@pytest.fixture
def mock_github_oauth_token_private_email(mock_github_user_private_email):
    """Create a mock GitHub OAuth token with private email userinfo."""
    return {
        "access_token": "test_github_token",
        "token_type": "bearer",
        "scope": "read:user user:email",
        "userinfo": mock_github_user_private_email,
    }


@pytest.fixture
def mock_gitlab_oauth_token(mock_gitlab_user_response):
    """Create a mock GitLab OAuth token with userinfo."""
    return {
        "access_token": "test_gitlab_token",
        "token_type": "bearer",
        "scope": "read_user read_api",
        "userinfo": mock_gitlab_user_response,
    }


@pytest.fixture
def mock_google_oauth_token(mock_google_user_response):
    """Create a mock Google OAuth token with userinfo."""
    return {
        "access_token": "test_google_token",
        "token_type": "bearer",
        "scope": "openid email profile",
        "userinfo": mock_google_user_response,
    }
