"""Tests for multi-provider authentication endpoints."""

from unittest.mock import AsyncMock, Mock, patch

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from api.models import OrganizationMembership, ProviderIdentity, User
from api.routers.auth.jwt import create_access_token, verify_access_token
from tests.utils.factories import OrganizationFactory, ProviderIdentityFactory, UserFactory

# =============================================================================
# Auth Login Tests (Multiple Providers)
# =============================================================================


def test_github_login_redirects(client: TestClient):
    """Test that GET /auth/github initiates OAuth flow."""
    response = client.get("/auth/github", follow_redirects=False)

    assert response.status_code == 302
    assert "github.com/login/oauth/authorize" in response.headers["location"]
    assert "client_id=test-github-client-id" in response.headers["location"]


@patch("api.routers.auth.handlers.get_oauth_client")
def test_google_login_redirects(mock_get_client: Mock, client: TestClient):
    """Test that GET /auth/google initiates OAuth flow."""
    mock_oauth_client = AsyncMock()
    mock_oauth_client.authorize_redirect = AsyncMock(
        return_value=RedirectResponse(
            "https://accounts.google.com/o/oauth2/auth?client_id=test-google-client-id"
        )
    )
    mock_get_client.return_value = mock_oauth_client

    response = client.get("/auth/google", follow_redirects=False)

    assert response.status_code == 307
    assert "accounts.google.com" in response.headers["location"]
    assert "client_id=test-google-client-id" in response.headers["location"]


@patch("api.routers.auth.handlers.get_oauth_client")
def test_gitlab_login_redirects(mock_get_client: Mock, client: TestClient):
    """Test that GET /auth/gitlab initiates OAuth flow."""
    mock_oauth_client = AsyncMock()
    mock_oauth_client.authorize_redirect = AsyncMock(
        return_value=RedirectResponse(
            "https://gitlab.com/oauth/authorize?client_id=test-gitlab-client-id"
        )
    )
    mock_get_client.return_value = mock_oauth_client

    response = client.get("/auth/gitlab", follow_redirects=False)

    assert response.status_code == 307
    assert "gitlab.com/oauth/authorize" in response.headers["location"]
    assert "client_id=test-gitlab-client-id" in response.headers["location"]


# =============================================================================
# GitHub OAuth Callback Tests
# =============================================================================


@patch("api.plugins.faststream.get_faststream_broker")
@patch("api.routers.auth.handlers.get_oauth_client")
def test_github_callback_creates_new_user(
    mock_get_client: Mock,
    mock_broker: Mock,
    client: TestClient,
    db_session: Session,
):
    """Test that GitHub callback creates a new user."""
    # Mock broker to prevent Redis connection
    mock_broker.return_value.publish = AsyncMock()

    # Mock OAuth client with userinfo in token
    mock_oauth_client = AsyncMock()
    mock_oauth_client.authorize_access_token = AsyncMock(
        return_value={
            "access_token": "test_token",
            "token_type": "bearer",
            "scope": "read:user",
            "userinfo": {
                "id": 12345,
                "login": "githubuser",
                "email": "github@example.com",
                "name": "GitHub User",
                "avatar_url": "https://avatars.githubusercontent.com/u/12345",
                "html_url": "https://github.com/githubuser",
            },
        }
    )
    mock_get_client.return_value = mock_oauth_client

    # Make request
    response = client.get(
        "/auth/callback/github", params={"code": "test_code"}, follow_redirects=False
    )

    # Verify redirect
    assert response.status_code in [302, 307]
    assert response.headers["location"].startswith("http://localhost:3000/")
    assert "reviewate_session" in response.headers.get("set-cookie", "")

    # Verify user created via ProviderIdentity
    identity = (
        db_session.query(ProviderIdentity)
        .filter(ProviderIdentity.provider == "github", ProviderIdentity.external_id == "12345")
        .first()
    )
    assert identity is not None
    assert identity.user_id is not None
    user = db_session.query(User).filter(User.id == identity.user_id).first()
    assert user is not None
    assert user.email == "github@example.com"
    assert identity.username == "githubuser"


@patch("api.plugins.faststream.get_faststream_broker")
@patch("api.routers.auth.handlers.get_oauth_client")
def test_github_callback_handles_private_email(
    mock_get_client: Mock,
    mock_broker: Mock,
    client: TestClient,
    db_session: Session,
):
    """Test that GitHub callback uses fallback email for private emails."""
    # Mock broker to prevent Redis connection
    mock_broker.return_value.publish = AsyncMock()

    # Mock OAuth client with no email in userinfo
    mock_oauth_client = AsyncMock()
    mock_oauth_client.authorize_access_token = AsyncMock(
        return_value={
            "access_token": "test_token",
            "token_type": "bearer",
            "scope": "read:user",
            "userinfo": {
                "id": 12345,
                "login": "privateuser",
                "email": None,  # Private email
                "name": "Private User",
                "avatar_url": "https://avatars.githubusercontent.com/u/12345",
                "html_url": "https://github.com/privateuser",
            },
        }
    )
    mock_get_client.return_value = mock_oauth_client

    # Make request
    response = client.get(
        "/auth/callback/github", params={"code": "test_code"}, follow_redirects=False
    )

    # Verify success
    assert response.status_code in [302, 307]

    # Verify fallback email was used via ProviderIdentity
    identity = (
        db_session.query(ProviderIdentity)
        .filter(ProviderIdentity.provider == "github", ProviderIdentity.external_id == "12345")
        .first()
    )
    assert identity is not None
    user = db_session.query(User).filter(User.id == identity.user_id).first()
    assert user is not None
    assert user.email == "privateuser@users.noreply.github.com"


# =============================================================================
# Google OAuth Callback Tests
# =============================================================================


@patch("api.routers.auth.handlers.get_oauth_client")
def test_google_callback_creates_new_user(
    mock_get_client: Mock,
    client: TestClient,
    db_session: Session,
):
    """Test that Google callback creates a new user."""
    # Mock OAuth client
    mock_oauth_client = AsyncMock()
    mock_oauth_client.authorize_access_token = AsyncMock(
        return_value={
            "access_token": "test_token",
            "token_type": "bearer",
            "scope": "openid email profile",
            "userinfo": {
                "sub": "google123456",
                "email": "google@example.com",
                "name": "Google User",
            },
        }
    )
    mock_get_client.return_value = mock_oauth_client

    # Make request
    response = client.get(
        "/auth/callback/google", params={"code": "test_code"}, follow_redirects=False
    )

    # Verify redirect
    assert response.status_code in [302, 307]
    assert "session" in response.headers.get("set-cookie", "")

    # Verify user created via ProviderIdentity
    identity = (
        db_session.query(ProviderIdentity)
        .filter(
            ProviderIdentity.provider == "google", ProviderIdentity.external_id == "google123456"
        )
        .first()
    )
    assert identity is not None
    user = db_session.query(User).filter(User.id == identity.user_id).first()
    assert user is not None
    assert user.email == "google@example.com"
    # Google users don't have platform username, just email


# =============================================================================
# GitLab OAuth Callback Tests
# =============================================================================


@patch("api.plugins.faststream.get_faststream_broker")
@patch("api.routers.auth.handlers.get_oauth_client")
def test_gitlab_callback_creates_new_user(
    mock_get_client: Mock,
    mock_broker: Mock,
    client: TestClient,
    db_session: Session,
    test_app,
):
    """Test that GitLab callback creates a new user."""
    # Mock broker to prevent Redis connection
    mock_broker.return_value.publish = AsyncMock()

    # Mock OAuth client
    mock_oauth_client = AsyncMock()
    mock_oauth_client.authorize_access_token = AsyncMock(
        return_value={
            "access_token": "test_token",
            "token_type": "bearer",
            "scope": "read_user",
        }
    )
    mock_get_client.return_value = mock_oauth_client

    # Mock the GitLab plugin's verify_token method to return userinfo
    with patch.object(
        test_app.gitlab,
        "verify_token",
        new_callable=AsyncMock,
        return_value={
            "id": 54321,
            "username": "gitlabuser",
            "email": "gitlab@example.com",
            "name": "GitLab User",
            "avatar_url": "https://gitlab.com/uploads/-/system/user/avatar/54321/avatar.png",
            "web_url": "https://gitlab.com/gitlabuser",
        },
    ):
        # Make request
        response = client.get(
            "/auth/callback/gitlab", params={"code": "test_code"}, follow_redirects=False
        )

        # Verify redirect
        assert response.status_code in [302, 307]
        assert "session" in response.headers.get("set-cookie", "")

        # Verify user created via ProviderIdentity
        identity = (
            db_session.query(ProviderIdentity)
            .filter(ProviderIdentity.provider == "gitlab", ProviderIdentity.external_id == "54321")
            .first()
        )
        assert identity is not None
        user = db_session.query(User).filter(User.id == identity.user_id).first()
        assert user is not None
        assert user.email == "gitlab@example.com"
        assert identity.username == "gitlabuser"


# =============================================================================
# User Update Tests
# =============================================================================


@patch("api.plugins.faststream.get_faststream_broker")
@patch("api.routers.auth.handlers.get_oauth_client")
def test_callback_updates_existing_user(
    mock_get_client: Mock,
    mock_broker: Mock,
    client: TestClient,
    db_session: Session,
):
    """Test that callback updates an existing user's info."""
    # Mock broker to prevent Redis connection
    mock_broker.return_value.publish = AsyncMock()

    # Create existing user with a provider identity
    existing_user = UserFactory.build(email="old@example.com")
    db_session.add(existing_user)
    db_session.commit()

    # Create provider identity for the user
    existing_identity = ProviderIdentityFactory.build(
        provider="github",
        external_id="12345",
        username="oldusername",
        user_id=existing_user.id,
    )
    db_session.add(existing_identity)
    db_session.commit()

    # Mock OAuth client with updated data
    mock_oauth_client = AsyncMock()
    mock_oauth_client.authorize_access_token = AsyncMock(
        return_value={
            "access_token": "test_token",
            "token_type": "bearer",
            "scope": "read:user",
            "userinfo": {
                "id": 12345,
                "login": "newusername",
                "email": "new@example.com",
                "name": "New User",
            },
        }
    )
    mock_get_client.return_value = mock_oauth_client

    # Make request
    response = client.get(
        "/auth/callback/github", params={"code": "test_code"}, follow_redirects=False
    )

    # Verify success
    assert response.status_code in [302, 307]

    # Verify user was updated
    db_session.refresh(existing_user)
    db_session.refresh(existing_identity)
    assert existing_user.email == "new@example.com"
    assert existing_identity.username == "newusername"


# =============================================================================
# Auth Me Tests
# =============================================================================


def test_me_returns_user_profile(
    authenticated_client: TestClient, create_user: User, create_identity: ProviderIdentity
):
    """Test that /auth/me returns the current user's profile."""
    response = authenticated_client.get("/auth/me")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(create_user.id)
    assert data["email"] == create_user.email
    # Identity fields come from ProviderIdentity
    assert data["github_username"] == create_identity.username
    assert data["github_external_id"] == create_identity.external_id
    # GitLab and Google are None since we only created a GitHub identity
    assert data["gitlab_username"] is None
    assert data["gitlab_external_id"] is None
    assert data["google_external_id"] is None
    assert "display_username" in data


def test_me_requires_authentication(client: TestClient):
    """Test that /auth/me requires authentication."""
    response = client.get("/auth/me")

    assert response.status_code == 401


# =============================================================================
# Auth Logout Tests
# =============================================================================


def test_logout_clears_session_cookie(authenticated_client: TestClient):
    """Test that /auth/logout clears the session cookie."""
    response = authenticated_client.post("/auth/logout")

    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully"
    # Check that cookie is cleared (max_age=0)
    set_cookie = response.headers.get("set-cookie", "")
    assert "session" in set_cookie
    assert "max-age=0" in set_cookie.lower() or "max_age=0" in set_cookie.lower()


def test_logout_works_without_session(client: TestClient):
    """Test that /auth/logout works even without a session."""
    response = client.post("/auth/logout")

    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully"


# =============================================================================
# JWT Token Tests
# =============================================================================


def test_create_and_verify_token(create_user: User, test_app):
    """Test creating and verifying a JWT token."""
    token = create_access_token(create_user.id)

    assert token is not None
    assert isinstance(token, str)

    # Verify token
    user_id = verify_access_token(token)
    assert user_id == create_user.id


def test_verify_invalid_token_raises_error(test_app):
    """Test that verifying an invalid token raises an error."""
    with pytest.raises(HTTPException):  # Will raise HTTPException
        verify_access_token("invalid.token.here")


def test_token_contains_user_id(create_user: User, test_app):
    """Test that the token contains the user ID in the payload."""
    token = create_access_token(create_user.id)
    payload = jwt.decode(token, options={"verify_signature": False})

    assert payload["sub"] == str(create_user.id)
    assert "exp" in payload
    assert "iat" in payload


# =============================================================================
# Organization Membership Tests
# =============================================================================


@patch("api.plugins.faststream.get_faststream_broker")
@patch("api.routers.auth.handlers.get_oauth_client")
def test_github_callback_does_not_sync_orgs_for_existing_user(
    mock_get_client: Mock,
    mock_broker: Mock,
    client: TestClient,
    db_session: Session,
):
    """Test that GitHub callback does NOT sync organizations for existing users."""
    # Mock broker to prevent Redis connection
    mock_broker.return_value.publish = AsyncMock()

    # Create existing user with provider identity and organization
    existing_user = UserFactory.build(email="existing@example.com")
    existing_org = OrganizationFactory.build(
        name="NewOrg",
        external_org_id="999",
        installation_id="install-999",
        provider="github",
        provider_url="https://github.com",
    )
    db_session.add_all([existing_user, existing_org])
    db_session.commit()

    # Create provider identity for the user
    existing_identity = ProviderIdentityFactory.build(
        provider="github",
        external_id="88888",
        username="existinguser",
        user_id=existing_user.id,
    )
    db_session.add(existing_identity)
    db_session.commit()

    # Mock OAuth client with userinfo
    mock_oauth_client = AsyncMock()
    mock_oauth_client.authorize_access_token = AsyncMock(
        return_value={
            "access_token": "test_token",
            "token_type": "bearer",
            "scope": "read:user,read:org",
            "userinfo": {
                "id": 88888,
                "login": "existinguser",
                "email": "existing@example.com",
                "name": "Existing User",
            },
        }
    )
    mock_get_client.return_value = mock_oauth_client

    # Execute
    response = client.get(
        "/auth/callback/github", params={"code": "test_code"}, follow_redirects=False
    )

    # Verify - no membership created for existing user
    assert response.status_code in [302, 307]

    identity = (
        db_session.query(ProviderIdentity)
        .filter(ProviderIdentity.provider == "github", ProviderIdentity.external_id == "88888")
        .first()
    )
    assert identity is not None

    # Query membership via provider_identity_id
    membership_count = (
        db_session.query(OrganizationMembership)
        .filter_by(provider_identity_id=identity.id, organization_id=existing_org.id)
        .count()
    )
    assert membership_count == 0
