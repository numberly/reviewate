"""Shared pytest fixtures for all tests.

This file imports all fixtures from the utils modules to make them available
to all tests. The actual fixture definitions are organized in tests/utils/.
"""

# Import app fixtures (includes test_config)
from tests.utils.app import authenticated_client, client, test_app, test_config

# Import auth fixtures (includes organization, repository, pull request fixtures)
from tests.utils.auth import (
    create_identity,
    create_organization,
    create_pull_request,
    create_repository,
    create_second_user,
    create_user,
    expired_jwt_token,
    invalid_jwt_token,
    jwt_token,
    mock_github_emails,
    mock_github_user_data,
    user_with_organization,
)

# Import database fixtures
from tests.utils.database import db_engine, db_session

# Import security fixtures
from tests.utils.security import generate_encryption_key

# Import service fixtures
from tests.utils.services import (
    TEST_CONFIG_PATH,
    mock_github_app_private_key,
    mock_github_installation_token_response,
    mock_github_installations_response,
    mock_github_organizations_response,
    mock_github_repositories_response,
    mock_github_user_private_email,
    mock_github_user_response,
    mock_gitlab_groups_response,
    mock_gitlab_user_response,
    mock_google_user_response,
    mock_httpx_client,
    mock_httpx_error_response,
    mock_httpx_response,
    mock_oauth_client,
    setup_github_mocks,
    setup_gitlab_mocks,
    setup_google_mocks,
)

# Re-export all fixtures to avoid "unused import" warnings
__all__ = [  # type: ignore
    # App fixtures
    "authenticated_client",
    "client",
    "test_app",
    "test_config",
    # Auth, Organization, Repository, Pull Request fixtures
    "create_identity",
    "create_organization",
    "create_pull_request",
    "create_repository",
    "create_second_user",
    "create_user",
    "expired_jwt_token",
    "invalid_jwt_token",
    "jwt_token",
    "mock_github_emails",
    "mock_github_user_data",
    "user_with_organization",
    # Database fixtures
    "db_engine",
    "db_session",
    # Service fixtures
    "TEST_CONFIG_PATH",
    "mock_github_app_private_key",
    "mock_github_installations_response",
    "mock_github_installation_token_response",
    "mock_github_organizations_response",
    "mock_github_repositories_response",
    "mock_github_user_private_email",
    "mock_github_user_response",
    "mock_gitlab_groups_response",
    "mock_gitlab_user_response",
    "mock_google_user_response",
    "mock_httpx_client",
    "mock_httpx_error_response",
    "mock_httpx_response",
    "mock_oauth_client",
    "setup_github_mocks",
    "setup_gitlab_mocks",
    "setup_google_mocks",
    # Security fixtures
    "generate_encryption_key",
]
