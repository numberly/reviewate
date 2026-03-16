"""Tests for organization settings endpoints."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.models import Organization, OrganizationMembership, User
from tests.utils.factories import OrganizationMembershipFactory, ProviderIdentityFactory

# =============================================================================
# GET Organization Settings Tests
# =============================================================================


def test_get_organization_settings_returns_defaults(
    authenticated_client: TestClient,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
):
    """Test that GET /organizations/{org_id}/settings returns default settings."""
    _, org, _ = user_with_organization

    response = authenticated_client.get(f"/organizations/{org.id}/settings")

    assert response.status_code == 200
    data = response.json()
    assert data["automatic_review_trigger"] == "none"
    assert data["automatic_summary_trigger"] == "never"


def test_get_organization_settings_requires_membership(
    authenticated_client: TestClient,
    create_organization: Organization,
):
    """Test that GET /organizations/{org_id}/settings requires membership."""
    # User has no membership in this organization
    response = authenticated_client.get(f"/organizations/{create_organization.id}/settings")

    assert response.status_code == 403
    assert "don't have access" in response.json()["detail"]


def test_get_organization_settings_requires_authentication(
    client: TestClient,
    create_organization: Organization,
):
    """Test that GET /organizations/{org_id}/settings requires authentication."""
    response = client.get(f"/organizations/{create_organization.id}/settings")

    assert response.status_code == 401


# =============================================================================
# PATCH Organization Settings Tests
# =============================================================================


def test_update_organization_settings_as_admin(
    authenticated_client: TestClient,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
):
    """Test that admin can update organization settings."""
    _, org, _ = user_with_organization

    response = authenticated_client.patch(
        f"/organizations/{org.id}/settings",
        json={
            "automatic_review_trigger": "creation",
            "automatic_summary_trigger": "creation",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["automatic_review_trigger"] == "creation"
    assert data["automatic_summary_trigger"] == "creation"


def test_update_organization_settings_partial_update(
    authenticated_client: TestClient,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
):
    """Test that partial updates work correctly."""
    _, org, _ = user_with_organization

    # Only update one field
    response = authenticated_client.patch(
        f"/organizations/{org.id}/settings",
        json={"automatic_review_trigger": "commit"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["automatic_review_trigger"] == "commit"
    # Other fields remain at defaults
    assert data["automatic_summary_trigger"] == "never"


def test_update_organization_settings_requires_admin(
    authenticated_client: TestClient,
    db_session: Session,
    create_user: User,
    create_organization: Organization,
):
    """Test that non-admin cannot update settings."""
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

    response = authenticated_client.patch(
        f"/organizations/{create_organization.id}/settings",
        json={"automatic_summary_trigger": "label"},
    )

    assert response.status_code == 403
    assert "admin" in response.json()["detail"].lower()


def test_update_organization_settings_requires_membership(
    authenticated_client: TestClient,
    create_organization: Organization,
):
    """Test that non-member cannot update settings."""
    response = authenticated_client.patch(
        f"/organizations/{create_organization.id}/settings",
        json={"automatic_summary_trigger": "label"},
    )

    assert response.status_code == 403


def test_update_organization_settings_invalid_trigger_value(
    authenticated_client: TestClient,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
):
    """Test that invalid trigger value is rejected."""
    _, org, _ = user_with_organization

    response = authenticated_client.patch(
        f"/organizations/{org.id}/settings",
        json={"automatic_review_trigger": "invalid_value"},
    )

    assert response.status_code == 422  # Validation error
