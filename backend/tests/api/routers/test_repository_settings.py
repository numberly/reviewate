"""Tests for repository settings endpoints."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.models import Organization, OrganizationMembership, User
from tests.utils.factories import (
    OrganizationMembershipFactory,
    ProviderIdentityFactory,
    RepositoryFactory,
)

# =============================================================================
# GET Repository Settings Tests
# =============================================================================


def test_get_repository_settings_returns_nulls(
    authenticated_client: TestClient,
    db_session: Session,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
):
    """Test that GET /repositories/{repo_id}/settings returns null values (inherits from org)."""
    _, org, _ = user_with_organization

    # Create repository
    repo = RepositoryFactory.build(organization_id=org.id)
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    response = authenticated_client.get(f"/repositories/{repo.id}/settings")

    assert response.status_code == 200
    data = response.json()
    assert data["automatic_review_trigger"] is None
    assert data["automatic_summary_trigger"] is None


def test_get_repository_settings_requires_membership(
    authenticated_client: TestClient,
    db_session: Session,
    create_organization: Organization,
):
    """Test that GET /repositories/{repo_id}/settings requires org membership."""
    # Create repository in org where user has no membership
    repo = RepositoryFactory.build(organization_id=create_organization.id)
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    response = authenticated_client.get(f"/repositories/{repo.id}/settings")

    assert response.status_code == 403
    assert "don't have access" in response.json()["detail"]


def test_get_repository_settings_not_found(
    authenticated_client: TestClient,
):
    """Test that GET returns 404 for non-existent repository."""
    import uuid

    fake_id = str(uuid.uuid4())
    response = authenticated_client.get(f"/repositories/{fake_id}/settings")

    assert response.status_code == 404


def test_get_repository_settings_requires_authentication(
    client: TestClient,
    db_session: Session,
    create_organization: Organization,
):
    """Test that GET /repositories/{repo_id}/settings requires authentication."""
    repo = RepositoryFactory.build(organization_id=create_organization.id)
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    response = client.get(f"/repositories/{repo.id}/settings")

    assert response.status_code == 401


# =============================================================================
# PATCH Repository Settings Tests
# =============================================================================


def test_update_repository_settings_as_admin(
    authenticated_client: TestClient,
    db_session: Session,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
):
    """Test that admin can update repository settings."""
    _, org, _ = user_with_organization

    repo = RepositoryFactory.build(organization_id=org.id)
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    response = authenticated_client.patch(
        f"/repositories/{repo.id}/settings",
        json={
            "automatic_review_trigger": "commit",
            "automatic_summary_trigger": "label",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["automatic_review_trigger"] == "commit"
    assert data["automatic_summary_trigger"] == "label"


def test_update_repository_settings_partial_update(
    authenticated_client: TestClient,
    db_session: Session,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
):
    """Test that partial updates work correctly."""
    _, org, _ = user_with_organization

    repo = RepositoryFactory.build(organization_id=org.id)
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    # Only update one field
    response = authenticated_client.patch(
        f"/repositories/{repo.id}/settings",
        json={"automatic_review_trigger": "creation"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["automatic_review_trigger"] == "creation"
    # Other fields remain null (inherit from org)
    assert data["automatic_summary_trigger"] is None


def test_update_repository_settings_requires_admin(
    authenticated_client: TestClient,
    db_session: Session,
    create_user: User,
    create_organization: Organization,
):
    """Test that non-admin cannot update repository settings."""
    # Create provider identity for the user
    identity = ProviderIdentityFactory.build(
        provider="github",
        external_id="12345",
        user_id=create_user.id,
    )
    db_session.add(identity)
    db_session.flush()

    # Create membership with member role (not admin) using provider_identity_id
    membership = OrganizationMembershipFactory.build(
        provider_identity_id=identity.id,
        organization_id=create_organization.id,
        role="member",
    )
    db_session.add(membership)
    db_session.commit()

    repo = RepositoryFactory.build(organization_id=create_organization.id)
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    response = authenticated_client.patch(
        f"/repositories/{repo.id}/settings",
        json={"automatic_summary_trigger": "label"},
    )

    assert response.status_code == 403
    assert "admin" in response.json()["detail"].lower()


def test_update_repository_settings_requires_membership(
    authenticated_client: TestClient,
    db_session: Session,
    create_organization: Organization,
):
    """Test that non-member cannot update repository settings."""
    repo = RepositoryFactory.build(organization_id=create_organization.id)
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    response = authenticated_client.patch(
        f"/repositories/{repo.id}/settings",
        json={"automatic_summary_trigger": "label"},
    )

    assert response.status_code == 403


def test_update_repository_settings_invalid_trigger_value(
    authenticated_client: TestClient,
    db_session: Session,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
):
    """Test that invalid trigger value is rejected."""
    _, org, _ = user_with_organization

    repo = RepositoryFactory.build(organization_id=org.id)
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    response = authenticated_client.patch(
        f"/repositories/{repo.id}/settings",
        json={"automatic_review_trigger": "invalid_value"},
    )

    assert response.status_code == 422  # Validation error


# =============================================================================
# DELETE Repository Settings Tests (Reset to Org Defaults)
# =============================================================================


def test_reset_repository_settings_as_admin(
    authenticated_client: TestClient,
    db_session: Session,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
):
    """Test that admin can reset repository settings to inherit from org."""
    _, org, _ = user_with_organization

    repo = RepositoryFactory.build(organization_id=org.id)
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    # First set some settings
    authenticated_client.patch(
        f"/repositories/{repo.id}/settings",
        json={
            "automatic_review_trigger": "commit",
            "automatic_summary_trigger": "label",
        },
    )

    # Reset settings
    response = authenticated_client.delete(f"/repositories/{repo.id}/settings")

    assert response.status_code == 200
    data = response.json()
    assert data["automatic_review_trigger"] is None
    assert data["automatic_summary_trigger"] is None


def test_reset_repository_settings_requires_admin(
    authenticated_client: TestClient,
    db_session: Session,
    create_user: User,
    create_organization: Organization,
):
    """Test that non-admin cannot reset repository settings."""
    # Create provider identity for the user
    identity = ProviderIdentityFactory.build(
        provider="github",
        external_id="12345",
        user_id=create_user.id,
    )
    db_session.add(identity)
    db_session.flush()

    # Create membership with member role (not admin) using provider_identity_id
    membership = OrganizationMembershipFactory.build(
        provider_identity_id=identity.id,
        organization_id=create_organization.id,
        role="member",
    )
    db_session.add(membership)
    db_session.commit()

    repo = RepositoryFactory.build(organization_id=create_organization.id)
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    response = authenticated_client.delete(f"/repositories/{repo.id}/settings")

    assert response.status_code == 403
    assert "admin" in response.json()["detail"].lower()


def test_reset_repository_settings_requires_membership(
    authenticated_client: TestClient,
    db_session: Session,
    create_organization: Organization,
):
    """Test that non-member cannot reset repository settings."""
    repo = RepositoryFactory.build(organization_id=create_organization.id)
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    response = authenticated_client.delete(f"/repositories/{repo.id}/settings")

    assert response.status_code == 403


def test_reset_repository_settings_not_found(
    authenticated_client: TestClient,
):
    """Test that DELETE returns 404 for non-existent repository."""
    import uuid

    fake_id = str(uuid.uuid4())
    response = authenticated_client.delete(f"/repositories/{fake_id}/settings")

    assert response.status_code == 404
