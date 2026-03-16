"""Tests for GitHub source handlers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.utils.factories import (
    OrganizationFactory,
    OrganizationMembershipFactory,
    ProviderIdentityFactory,
)


@pytest.mark.asyncio
async def test_get_github_install_url_success(authenticated_client, test_app):
    """Test getting GitHub App installation URL."""
    response = authenticated_client.get("/sources/github/install-url")

    assert response.status_code == 200
    data = response.json()
    assert "url" in data
    assert "app_name" in data
    assert "https://github.com/apps/" in data["url"]
    assert "/installations/new" in data["url"]


@pytest.mark.asyncio
async def test_uninstall_github_app_success(
    authenticated_client, db_session, create_user, test_app
):
    """Test successful GitHub App uninstallation."""
    user = create_user

    # Create organization using factory
    org = OrganizationFactory.build(
        name="Test Org",
        external_org_id="12345",
        installation_id="67890",
        provider="github",
        provider_url="https://github.com",
    )
    db_session.add(org)
    db_session.flush()

    # Create provider identity for the user
    identity = ProviderIdentityFactory.build(
        provider="github",
        external_id="12345",
        user_id=user.id,
    )
    db_session.add(identity)
    db_session.flush()

    # Create admin membership using provider_identity_id
    membership = OrganizationMembershipFactory.build(
        provider_identity_id=identity.id,
        organization_id=org.id,
        role="admin",
    )
    db_session.add(membership)
    db_session.commit()

    # Mock GitHub API response
    with (
        patch.object(test_app.github, "_generate_jwt", return_value="fake-jwt-token"),
        patch.object(test_app.github.http, "delete", new_callable=AsyncMock) as mock_delete,
    ):
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.text = ""
        mock_delete.return_value = mock_response

        response = authenticated_client.delete(f"/sources/github/installations/{org.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Test Org" in data["message"]

        # Verify GitHub API was called
        mock_delete.assert_called_once()
        call_args = mock_delete.call_args
        assert f"/app/installations/{org.installation_id}" in str(call_args)


@pytest.mark.asyncio
async def test_uninstall_github_app_invalid_uuid(authenticated_client):
    """Test uninstallation with invalid UUID."""
    response = authenticated_client.delete("/sources/github/installations/invalid-uuid")

    assert response.status_code == 400
    assert "organization ID" in response.json()["detail"]


@pytest.mark.asyncio
async def test_uninstall_github_app_not_found(authenticated_client, create_user):
    """Test uninstallation of non-existent organization returns 403 (no membership)."""
    response = authenticated_client.delete(
        "/sources/github/installations/00000000-0000-0000-0000-000000000000"
    )

    # verify_organization_admin dependency returns 403 when user has no membership
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_uninstall_github_app_no_permission(
    authenticated_client, db_session, create_user, create_second_user
):
    """Test uninstallation without admin permission."""
    # Create organization owned by another user using factory
    org = OrganizationFactory.build(
        name="Other User Org",
        external_org_id="99999",
        installation_id="88888",
        provider="github",
        provider_url="https://github.com",
    )
    db_session.add(org)
    db_session.flush()

    # Create provider identity for the user
    identity = ProviderIdentityFactory.build(
        provider="github",
        external_id="99999",
        user_id=create_user.id,
    )
    db_session.add(identity)
    db_session.flush()

    # Create non-admin membership for current user using provider_identity_id
    membership = OrganizationMembershipFactory.build(
        provider_identity_id=identity.id,
        organization_id=org.id,
        role="member",  # Not admin
    )
    db_session.add(membership)
    db_session.commit()

    response = authenticated_client.delete(f"/sources/github/installations/{org.id}")

    assert response.status_code == 403
    assert "admin" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_uninstall_github_app_github_api_error(
    authenticated_client, db_session, create_user, test_app
):
    """Test uninstallation when GitHub API returns error."""
    user = create_user

    # Create organization using factory
    org = OrganizationFactory.build(
        name="Test Org",
        external_org_id="12345",
        installation_id="67890",
        provider="github",
        provider_url="https://github.com",
    )
    db_session.add(org)
    db_session.flush()

    # Create provider identity for the user
    identity = ProviderIdentityFactory.build(
        provider="github",
        external_id="12345",
        user_id=user.id,
    )
    db_session.add(identity)
    db_session.flush()

    # Create admin membership using provider_identity_id
    membership = OrganizationMembershipFactory.build(
        provider_identity_id=identity.id,
        organization_id=org.id,
        role="admin",
    )
    db_session.add(membership)
    db_session.commit()

    # Mock GitHub API error response
    with (
        patch.object(test_app.github, "_generate_jwt", return_value="fake-jwt-token"),
        patch.object(test_app.github.http, "delete", new_callable=AsyncMock) as mock_delete,
    ):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_delete.return_value = mock_response

        response = authenticated_client.delete(f"/sources/github/installations/{org.id}")

        assert response.status_code == 500
        assert "Failed to delete installation from GitHub" in response.json()["detail"]


@pytest.mark.asyncio
async def test_uninstall_github_app_already_deleted_on_github(
    authenticated_client, db_session, create_user, test_app
):
    """Test uninstallation when installation already deleted on GitHub (404)."""
    user = create_user

    # Create organization using factory
    org = OrganizationFactory.build(
        name="Test Org",
        external_org_id="12345",
        installation_id="67890",
        provider="github",
        provider_url="https://github.com",
    )
    db_session.add(org)
    db_session.flush()

    # Create provider identity for the user
    identity = ProviderIdentityFactory.build(
        provider="github",
        external_id="12345",
        user_id=user.id,
    )
    db_session.add(identity)
    db_session.flush()

    # Create admin membership using provider_identity_id
    membership = OrganizationMembershipFactory.build(
        provider_identity_id=identity.id,
        organization_id=org.id,
        role="admin",
    )
    db_session.add(membership)
    db_session.commit()

    # Mock GitHub API 404 response (installation already deleted)
    with (
        patch.object(test_app.github, "_generate_jwt", return_value="fake-jwt-token"),
        patch.object(test_app.github.http, "delete", new_callable=AsyncMock) as mock_delete,
    ):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_delete.return_value = mock_response

        response = authenticated_client.delete(f"/sources/github/installations/{org.id}")

        # Should still succeed (cleanup our DB even if GitHub already deleted)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


@pytest.mark.asyncio
async def test_uninstall_github_app_exception_during_github_call(
    authenticated_client, db_session, create_user, test_app
):
    """Test uninstallation when exception occurs during GitHub API call."""
    user = create_user

    # Create organization using factory
    org = OrganizationFactory.build(
        name="Test Org",
        external_org_id="12345",
        installation_id="67890",
        provider="github",
        provider_url="https://github.com",
    )
    db_session.add(org)
    db_session.flush()

    # Create provider identity for the user
    identity = ProviderIdentityFactory.build(
        provider="github",
        external_id="12345",
        user_id=user.id,
    )
    db_session.add(identity)
    db_session.flush()

    # Create admin membership using provider_identity_id
    membership = OrganizationMembershipFactory.build(
        provider_identity_id=identity.id,
        organization_id=org.id,
        role="admin",
    )
    db_session.add(membership)
    db_session.commit()

    # Mock GitHub API to raise exception
    with patch.object(test_app.github, "_generate_jwt", side_effect=Exception("Connection error")):
        response = authenticated_client.delete(f"/sources/github/installations/{org.id}")

        assert response.status_code == 500
        assert "Failed to delete installation from GitHub" in response.json()["detail"]
