"""Authentication and organization fixtures for testing."""

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from sqlalchemy.orm import Session

from api.models import (
    Organization,
    OrganizationMembership,
    ProviderIdentity,
    PullRequest,
    Repository,
    User,
)
from api.routers.auth import create_access_token
from tests.utils.factories import (
    OrganizationFactory,
    OrganizationMembershipFactory,
    ProviderIdentityFactory,
    PullRequestFactory,
    RepositoryFactory,
    UserFactory,
)


@pytest.fixture(scope="function")
def create_user(db_session: Session) -> User:
    """Create a test user in the database using UserFactory.

    Args:
        db_session: Database session fixture

    Returns:
        User: Test user instance
    """
    user = UserFactory.build()
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


@pytest.fixture(scope="function")
def create_second_user(db_session: Session) -> User:
    """Create another test user for multi-user tests using UserFactory.

    Args:
        db_session: Database session fixture

    Returns:
        User: Another test user instance
    """
    user = UserFactory.build()
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


@pytest.fixture(scope="function")
def create_identity(db_session: Session, create_user: User) -> ProviderIdentity:
    """Create a provider identity linked to the test user.

    Args:
        db_session: Database session fixture
        create_user: Test user fixture

    Returns:
        ProviderIdentity: Test identity instance linked to the user
    """
    identity = ProviderIdentityFactory.build(
        provider="github",
        user_id=create_user.id,
    )
    db_session.add(identity)
    db_session.commit()
    db_session.refresh(identity)

    return identity


@pytest.fixture(scope="function")
def jwt_token(create_user: User, test_app) -> str:
    """Create a valid JWT token for the test user.

    Args:
        create_user: Test user fixture

    Returns:
        str: JWT token string
    """
    return create_access_token(create_user.id)


@pytest.fixture(scope="function")
def expired_jwt_token() -> str:
    """Create an expired JWT token for testing.

    Returns:
        str: Expired JWT token string
    """
    # Use the same secret key as the application
    secret_key = os.getenv("JWT_SECRET_KEY", "test-key")

    payload = {
        "sub": str(uuid4()),
        "exp": datetime.now(UTC) - timedelta(days=1),  # Expired yesterday
        "iat": datetime.now(UTC) - timedelta(days=2),
    }

    return jwt.encode(payload, secret_key, algorithm="HS256")


@pytest.fixture(scope="function")
def invalid_jwt_token() -> str:
    """Create an invalid JWT token for testing.

    Returns:
        str: Invalid JWT token string
    """
    return "invalid.jwt.token"


@pytest.fixture
def mock_github_user_data():
    """Mock GitHub user data returned from OAuth.

    Returns:
        dict: Mock GitHub user data
    """
    return {
        "id": 123456,
        "login": "testuser",
        "email": "test@example.com",
        "name": "Test User",
        "avatar_url": "https://avatars.githubusercontent.com/u/123456",
    }


@pytest.fixture
def mock_github_emails():
    """Mock GitHub emails API response.

    Returns:
        list: Mock email data from GitHub
    """
    return [
        {
            "email": "test@example.com",
            "primary": True,
            "verified": True,
            "visibility": "public",
        },
        {
            "email": "private@example.com",
            "primary": False,
            "verified": True,
            "visibility": "private",
        },
    ]


# =============================================================================
# Organization Fixtures
# =============================================================================


@pytest.fixture(scope="function")
def create_organization(db_session: Session) -> Organization:  # type: ignore
    """Create a test organization in the database using OrganizationFactory.

    Args:
        db_session: Database session fixture

    Returns:
        Organization: Test organization instance
    """
    org = OrganizationFactory.build()
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)

    yield org

    # Cleanup
    db_session.delete(org)
    db_session.commit()


@pytest.fixture(scope="function")
def user_with_organization(
    db_session: Session, create_user: User, create_organization: Organization
) -> tuple[User, Organization, OrganizationMembership]:  # type: ignore
    """Create a user with an organization membership (composite fixture).

    This is a convenience fixture that combines user, organization, and membership.
    Internally creates a ProviderIdentity to link the user to the membership.

    Args:
        db_session: Database session fixture
        create_user: Test user fixture
        create_organization: Test organization fixture

    Returns:
        tuple: (User, Organization, OrganizationMembership)
    """
    # Create a provider identity for the user (required for membership)
    identity = ProviderIdentityFactory.build(
        provider="github",
        user_id=create_user.id,
    )
    db_session.add(identity)
    db_session.commit()
    db_session.refresh(identity)

    # Create organization membership using the identity
    membership = OrganizationMembershipFactory.build(
        provider_identity_id=identity.id,
        organization_id=create_organization.id,
        role="admin",
    )
    db_session.add(membership)
    db_session.commit()
    db_session.refresh(membership)

    yield create_user, create_organization, membership


# =============================================================================
# Repository Fixtures
# =============================================================================


@pytest.fixture(scope="function")
def create_repository(db_session: Session, create_organization: Organization) -> Repository:  # type: ignore
    """Create a test repository in the database using RepositoryFactory.

    Args:
        db_session: Database session fixture
        create_organization: Test organization fixture

    Returns:
        Repository: Test repository instance
    """
    repo = RepositoryFactory.build(organization_id=create_organization.id)
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    yield repo

    # Cleanup (if not already deleted by cascade)
    try:
        db_session.delete(repo)
        db_session.commit()
    except Exception:
        pass


# =============================================================================
# Pull Request Fixtures
# =============================================================================


@pytest.fixture(scope="function")
def create_pull_request(
    db_session: Session,
    create_organization: Organization,
    create_repository: Repository,
) -> PullRequest:  # type: ignore
    """Create a test pull request in the database using PullRequestFactory.

    Args:
        db_session: Database session fixture
        create_organization: Test organization fixture
        create_repository: Test repository fixture

    Returns:
        PullRequest: Test pull request instance
    """
    pr = PullRequestFactory.build(
        organization_id=create_organization.id,
        repository_id=create_repository.id,
    )
    db_session.add(pr)
    db_session.commit()
    db_session.refresh(pr)

    yield pr

    # Cleanup (if not already deleted by cascade)
    try:
        db_session.delete(pr)
        db_session.commit()
    except Exception:
        pass
