"""Tests for sources endpoints."""

from fastapi.testclient import TestClient

from api.models import Organization, OrganizationMembership, User

# =============================================================================
# List Sources Tests
# =============================================================================


def test_list_sources_returns_user_orgs(
    authenticated_client: TestClient,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
):
    """Test that GET /sources returns sources where user is a member."""
    _, org, _ = user_with_organization

    # Make request
    response = authenticated_client.get("/sources")

    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert "objects" in data
    assert len(data["objects"]) == 1

    # Verify organization data
    returned_org = data["objects"][0]
    assert returned_org["name"] == org.name
    assert returned_org["external_org_id"] == org.external_org_id
    assert returned_org["installation_id"] == org.installation_id

    # Verify structure
    assert "id" in returned_org
    assert "created_at" in returned_org


def test_list_sources_empty_when_no_memberships(
    authenticated_client: TestClient,
    create_organization: Organization,
):
    """Test that GET /sources returns empty list when user has no memberships."""
    # Organization exists but create_user (from authenticated_client) has no membership

    # Make request
    response = authenticated_client.get("/sources")

    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert "objects" in data
    assert len(data["objects"]) == 0


def test_list_sources_requires_authentication(client: TestClient):
    """Test that GET /sources requires authentication."""
    response = client.get("/sources")

    assert response.status_code == 401
