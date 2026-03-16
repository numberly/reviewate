"""Tests for sources endpoints."""

from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api.models import Organization, OrganizationMembership, Repository, RepositoryMembership
from api.plugins.gitlab.config import GitLabOAuthConfig, GitLabPluginConfig
from api.plugins.gitlab.plugin import GitLabPlugin
from api.plugins.gitlab.schemas import GitlabTokenType
from tests.utils.factories import ProviderIdentityFactory

# =============================================================================
# Add GitLab Source Tests
# =============================================================================


@pytest.mark.asyncio
@patch("api.routers.sources.gitlab.handlers.get_faststream_broker")
@patch("api.plugins.gitlab.plugin.GitLabPlugin.determine_user_role_in_group")
@patch("api.plugins.gitlab.plugin.GitLabPlugin.fetch_group")
@patch("api.plugins.gitlab.plugin.GitLabPlugin.get_token_type")
@patch("api.plugins.gitlab.plugin.GitLabPlugin.verify_token")
async def test_add_gitlab_group_token_creates_organization(
    mock_verify_token: Mock,
    mock_get_token_type: Mock,
    mock_fetch_group: Mock,
    mock_determine_role: Mock,
    mock_get_broker: Mock,
    authenticated_client: TestClient,
    test_app,
    db_session,
    create_user,
):
    """Test that adding a GitLab group token creates organization and queues repo sync."""
    # Create GitLab identity for the user (required for adding GitLab sources)
    identity = ProviderIdentityFactory.build(
        provider="gitlab",
        external_id="12345",
        user_id=create_user.id,
    )
    db_session.add(identity)
    db_session.commit()

    # Setup broker mock
    mock_broker = MagicMock()
    mock_broker.publish = AsyncMock(return_value=None)
    mock_get_broker.return_value = mock_broker

    # Setup mocks
    mock_verify_token.return_value = {
        "id": 2066,
        "username": "group_1114_bot_5b8ef5bc67f6d17ac71d3a7156c936c0",
        "name": "Reviewate",
        "bot": True,
    }
    mock_get_token_type.return_value = GitlabTokenType.GROUP_ACCESS_TOKEN
    mock_fetch_group.return_value = {
        "id": 1114,
        "name": "My Group",
        "path": "my-group",
        "parent_id": None,
    }
    mock_determine_role.return_value = "admin"

    # Make request
    response = authenticated_client.post(
        "/sources/gitlab",
        json={"access_token": "glpat-xxxxxxxxxxxxx"},
    )

    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["source_type"] == "group"
    assert data["source_name"] == "My Group"
    assert data["membership_created"] is True

    # Verify organization created
    org = db_session.query(Organization).filter(Organization.external_org_id == "1114").first()
    assert org is not None
    assert org.name == "My Group"
    assert org.gitlab_access_token_encrypted is not None

    # Verify organization membership created
    org_membership = (
        db_session.query(OrganizationMembership)
        .filter(OrganizationMembership.organization_id == org.id)
        .first()
    )
    assert org_membership is not None
    assert org_membership.role == "admin"

    # Verify repo sync was queued (not done inline)
    publish_calls = mock_broker.publish.call_args_list
    streams = [call.kwargs.get("stream") or call[1].get("stream") for call in publish_calls]
    assert "reviewate.events.gitlab.sync_group_repositories" in streams

    # Verify the message contains correct data
    repo_sync_call = next(
        call
        for call in publish_calls
        if (call.kwargs.get("stream") or call[1].get("stream"))
        == "reviewate.events.gitlab.sync_group_repositories"
    )
    message = repo_sync_call.args[0]
    assert message.organization_id == str(org.id)
    assert message.group_id == "1114"
    assert message.user_id == str(create_user.id)


@pytest.mark.asyncio
@patch("api.routers.sources.gitlab.handlers.get_faststream_broker")
@patch("api.plugins.gitlab.plugin.GitLabPlugin.determine_user_role_in_project")
@patch("api.plugins.gitlab.plugin.GitLabPlugin.fetch_project")
@patch("api.plugins.gitlab.plugin.GitLabPlugin.get_token_type")
@patch("api.plugins.gitlab.plugin.GitLabPlugin.verify_token")
async def test_add_gitlab_project_token_creates_repository(
    mock_verify_token: Mock,
    mock_get_token_type: Mock,
    mock_fetch_project: Mock,
    mock_determine_role: Mock,
    mock_get_broker: Mock,
    authenticated_client: TestClient,
    test_app,
    db_session,
    create_user,
):
    """Test that adding a GitLab project token creates a repository."""
    # Create GitLab identity for the user (required for adding GitLab sources)
    identity = ProviderIdentityFactory.build(
        provider="gitlab",
        external_id="12345",
        user_id=create_user.id,
    )
    db_session.add(identity)
    db_session.commit()

    # Setup broker mock
    mock_broker = MagicMock()
    mock_broker.publish = AsyncMock(return_value=None)
    mock_get_broker.return_value = mock_broker

    # Setup mocks
    mock_verify_token.return_value = {
        "id": 2072,
        "username": "project_7831_bot_16f0b650636d7345babdeacabdf25c2a",
        "name": "test token proj",
        "bot": True,
    }
    mock_get_token_type.return_value = GitlabTokenType.PROJECT_ACCESS_TOKEN
    mock_fetch_project.return_value = {
        "id": 7831,
        "name": "My Project",
        "path": "my-project",
        "web_url": "https://gitlab.com/my-namespace/my-project",
        "namespace": {"id": 789, "name": "My Namespace", "path": "my-namespace"},
    }
    mock_determine_role.return_value = "admin"

    # Make request
    response = authenticated_client.post(
        "/sources/gitlab",
        json={"access_token": "glpat-yyyyyyyyyyyy"},
    )

    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["source_type"] == "project"
    assert data["source_name"] == "My Project"
    assert data["membership_created"] is True

    # Verify repository created
    repo = db_session.query(Repository).filter(Repository.external_repo_id == "7831").first()
    assert repo is not None
    assert repo.name == "My Project"
    assert repo.web_url == "https://gitlab.com/my-namespace/my-project"
    assert repo.gitlab_access_token_encrypted is not None

    # Verify repository membership created
    membership = (
        db_session.query(RepositoryMembership)
        .filter(RepositoryMembership.repository_id == repo.id)
        .first()
    )
    assert membership is not None
    assert membership.role == "admin"


def test_add_gitlab_source_requires_authentication(client: TestClient):
    """Test that POST /sources/gitlab requires authentication."""
    response = client.post(
        "/sources/gitlab",
        json={"access_token": "glpat-xxxxxxxxxxxxx"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
@patch("api.plugins.gitlab.plugin.GitLabPlugin.verify_token")
async def test_add_gitlab_source_rejects_invalid_token(
    mock_verify_token: Mock,
    authenticated_client: TestClient,
    test_app,
):
    """Test that POST /sources/gitlab rejects invalid tokens."""

    # Setup mock to raise exception
    mock_verify_token.side_effect = HTTPException(status_code=401, detail="Invalid token")

    # Make request
    response = authenticated_client.post(
        "/sources/gitlab",
        json={"access_token": "invalid-token"},
    )

    # Verify error response
    assert response.status_code == 401
    assert "Failed to verify GitLab token" in response.json()["detail"]


@pytest.mark.asyncio
@patch("api.plugins.gitlab.plugin.GitLabPlugin.get_token_type")
@patch("api.plugins.gitlab.plugin.GitLabPlugin.verify_token")
async def test_add_gitlab_source_rejects_personal_token(
    mock_verify_token: Mock,
    mock_get_token_type: Mock,
    authenticated_client: TestClient,
    test_app,
):
    """Test that POST /sources/gitlab rejects personal tokens."""
    # Setup mocks
    mock_verify_token.return_value = {
        "id": 1517,
        "username": "adsa",
        "name": "Adam Saimi",
        "bot": False,
        "email": "adam.saimi@example.com",
    }
    mock_get_token_type.return_value = GitlabTokenType.PERSONAL_ACCESS_TOKEN

    # Make request
    response = authenticated_client.post(
        "/sources/gitlab",
        json={"access_token": "glpat-personal-token"},
    )

    # Verify error response
    assert response.status_code == 400
    assert "Token must be a group or project access token" in response.json()["detail"]


@patch("api.app.Application.gitlab", new_callable=PropertyMock)
def test_add_gitlab_source_fails_when_service_disabled(
    mock_gitlab_property: PropertyMock,
    authenticated_client: TestClient,
    test_app,
):
    """Test that POST /sources/gitlab fails when GitLab service is disabled."""

    # require_gitlab_enabled checks app.gitlab; None means plugin not loaded
    mock_gitlab_property.return_value = None

    # Make request
    response = authenticated_client.post(
        "/sources/gitlab",
        json={"access_token": "glpat-xxxxxxxxxxxxx"},
    )

    # Verify error response — require_gitlab_enabled returns 503
    assert response.status_code == 503


@pytest.mark.asyncio
@patch("api.plugins.gitlab.plugin.GitLabPlugin.determine_user_role_in_group")
@patch("api.plugins.gitlab.plugin.GitLabPlugin.fetch_group")
@patch("api.plugins.gitlab.plugin.GitLabPlugin.get_token_type")
@patch("api.plugins.gitlab.plugin.GitLabPlugin.verify_token")
async def test_add_gitlab_group_token_rejects_non_admin(
    mock_verify_token: Mock,
    mock_get_token_type: Mock,
    mock_fetch_group: Mock,
    mock_determine_role: Mock,
    authenticated_client: TestClient,
    test_app,
    db_session,
    create_user,
):
    """Test that adding a GitLab group token rejects non-admin users."""
    identity = ProviderIdentityFactory.build(
        provider="gitlab",
        external_id="12345",
        user_id=create_user.id,
    )
    db_session.add(identity)
    db_session.commit()

    mock_verify_token.return_value = {
        "id": 2066,
        "username": "group_1114_bot_5b8ef5bc67f6d17ac71d3a7156c936c0",
        "name": "Reviewate",
        "bot": True,
    }
    mock_get_token_type.return_value = GitlabTokenType.GROUP_ACCESS_TOKEN
    mock_fetch_group.return_value = {
        "id": 1114,
        "name": "My Group",
        "path": "my-group",
        "parent_id": None,
    }
    mock_determine_role.return_value = "member"

    response = authenticated_client.post(
        "/sources/gitlab",
        json={"access_token": "glpat-xxxxxxxxxxxxx"},
    )

    assert response.status_code == 403
    assert "Maintainer" in response.json()["detail"]


@pytest.mark.asyncio
@patch("api.plugins.gitlab.plugin.GitLabPlugin.determine_user_role_in_project")
@patch("api.plugins.gitlab.plugin.GitLabPlugin.fetch_project")
@patch("api.plugins.gitlab.plugin.GitLabPlugin.get_token_type")
@patch("api.plugins.gitlab.plugin.GitLabPlugin.verify_token")
async def test_add_gitlab_project_token_rejects_non_admin(
    mock_verify_token: Mock,
    mock_get_token_type: Mock,
    mock_fetch_project: Mock,
    mock_determine_role: Mock,
    authenticated_client: TestClient,
    test_app,
    db_session,
    create_user,
):
    """Test that adding a GitLab project token rejects non-admin users."""
    identity = ProviderIdentityFactory.build(
        provider="gitlab",
        external_id="12345",
        user_id=create_user.id,
    )
    db_session.add(identity)
    db_session.commit()

    mock_verify_token.return_value = {
        "id": 2072,
        "username": "project_7831_bot_16f0b650636d7345babdeacabdf25c2a",
        "name": "test token proj",
        "bot": True,
    }
    mock_get_token_type.return_value = GitlabTokenType.PROJECT_ACCESS_TOKEN
    mock_fetch_project.return_value = {
        "id": 7831,
        "name": "My Project",
        "path": "my-project",
        "web_url": "https://gitlab.com/my-namespace/my-project",
        "namespace": {"id": 789, "name": "My Namespace", "path": "my-namespace"},
    }
    mock_determine_role.return_value = "member"

    response = authenticated_client.post(
        "/sources/gitlab",
        json={"access_token": "glpat-yyyyyyyyyyyy"},
    )

    assert response.status_code == 403
    assert "Maintainer" in response.json()["detail"]


# =============================================================================
# fetch_group_projects Tests
# =============================================================================


@pytest.mark.asyncio
async def test_fetch_group_projects_excludes_shared_projects():
    """Test that fetch_group_projects passes with_shared=False to exclude shared projects."""
    config = GitLabPluginConfig(
        enabled=True,
        oauth=GitLabOAuthConfig(
            client_id="test",
            client_secret="test",
        ),
    )
    plugin = GitLabPlugin(plugin_config=config)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = []

    mock_http = MagicMock()
    mock_http.get = AsyncMock(return_value=mock_response)
    plugin._http = mock_http

    await plugin.fetch_group_projects(access_token="test-token", group_id="1114")

    mock_http.get.assert_called_once()
    call_kwargs = mock_http.get.call_args
    params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
    assert params["with_shared"] is False
    assert params["include_subgroups"] is True


# =============================================================================
# Subgroup + Root Group Upsert Tests
# =============================================================================


@pytest.mark.asyncio
@patch("api.routers.sources.gitlab.handlers.get_faststream_broker")
@patch("api.plugins.gitlab.plugin.GitLabPlugin.resolve_root_group")
@patch("api.plugins.gitlab.plugin.GitLabPlugin.determine_user_role_in_group")
@patch("api.plugins.gitlab.plugin.GitLabPlugin.fetch_group")
@patch("api.plugins.gitlab.plugin.GitLabPlugin.get_token_type")
@patch("api.plugins.gitlab.plugin.GitLabPlugin.verify_token")
async def test_add_gitlab_subgroup_token_creates_org_at_root_group(
    mock_verify_token: Mock,
    mock_get_token_type: Mock,
    mock_fetch_group: Mock,
    mock_determine_role: Mock,
    mock_resolve_root: Mock,
    mock_get_broker: Mock,
    authenticated_client: TestClient,
    test_app,
    db_session,
    create_user,
):
    """Test that a subgroup token creates the org at the root group, not the subgroup."""
    identity = ProviderIdentityFactory.build(
        provider="gitlab",
        external_id="12345",
        user_id=create_user.id,
    )
    db_session.add(identity)
    db_session.commit()

    mock_broker = MagicMock()
    mock_broker.publish = AsyncMock(return_value=None)
    mock_get_broker.return_value = mock_broker

    # Token belongs to subgroup 2222, whose root is group 1000
    mock_verify_token.return_value = {
        "id": 3000,
        "username": "group_2222_bot_abc123",
        "name": "Reviewate",
        "bot": True,
    }
    mock_get_token_type.return_value = GitlabTokenType.GROUP_ACCESS_TOKEN
    mock_fetch_group.return_value = {
        "id": 2222,
        "name": "My Subgroup",
        "path": "my-subgroup",
        "parent_id": 1000,
    }
    mock_determine_role.return_value = "admin"
    mock_resolve_root.return_value = {
        "id": 1000,
        "name": "Root Group",
        "path": "root-group",
        "parent_id": None,
        "avatar_url": "https://gitlab.com/root-avatar.png",
    }

    response = authenticated_client.post(
        "/sources/gitlab",
        json={"access_token": "glpat-subgroup-token"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["source_type"] == "group"
    assert data["source_name"] == "Root Group"

    # Org should be at root group ID, not subgroup
    org = db_session.query(Organization).filter(Organization.external_org_id == "1000").first()
    assert org is not None
    assert org.name == "Root Group"
    # Subgroup token should NOT be stored on the org
    assert org.gitlab_access_token_encrypted is None

    # No org should exist for the subgroup ID
    subgroup_org = (
        db_session.query(Organization).filter(Organization.external_org_id == "2222").first()
    )
    assert subgroup_org is None

    # Verify sync messages carry encrypted_token + store_token_on_repos
    publish_calls = mock_broker.publish.call_args_list
    repo_sync_call = next(
        call
        for call in publish_calls
        if (call.kwargs.get("stream") or call[1].get("stream"))
        == "reviewate.events.gitlab.sync_group_repositories"
    )
    repo_msg = repo_sync_call.args[0]
    assert repo_msg.group_id == "2222"
    assert repo_msg.encrypted_token is not None
    assert repo_msg.store_token_on_repos is True

    member_sync_call = next(
        call
        for call in publish_calls
        if (call.kwargs.get("stream") or call[1].get("stream"))
        == "reviewate.events.gitlab.sync_members"
    )
    member_msg = member_sync_call.args[0]
    assert member_msg.encrypted_token is not None


@pytest.mark.asyncio
@patch("api.routers.sources.gitlab.handlers.get_faststream_broker")
@patch("api.plugins.gitlab.plugin.GitLabPlugin.determine_user_role_in_group")
@patch("api.plugins.gitlab.plugin.GitLabPlugin.fetch_group")
@patch("api.plugins.gitlab.plugin.GitLabPlugin.get_token_type")
@patch("api.plugins.gitlab.plugin.GitLabPlugin.verify_token")
async def test_add_root_group_token_upserts_existing_org(
    mock_verify_token: Mock,
    mock_get_token_type: Mock,
    mock_fetch_group: Mock,
    mock_determine_role: Mock,
    mock_get_broker: Mock,
    authenticated_client: TestClient,
    test_app,
    db_session,
    create_user,
):
    """Test that adding a root group token upserts the token onto an existing org."""
    identity = ProviderIdentityFactory.build(
        provider="gitlab",
        external_id="12345",
        user_id=create_user.id,
    )
    db_session.add(identity)
    db_session.commit()

    # Pre-create org without a token (as would happen from a subgroup token)
    from api.database import db_create_organization

    existing_org = db_create_organization(
        db=db_session,
        name="Root Group",
        external_org_id="1000",
        installation_id="gitlab-group-1000",
        provider="gitlab",
        provider_url="https://gitlab.com",
        gitlab_access_token_encrypted=None,
    )
    db_session.commit()

    mock_broker = MagicMock()
    mock_broker.publish = AsyncMock(return_value=None)
    mock_get_broker.return_value = mock_broker

    mock_verify_token.return_value = {
        "id": 4000,
        "username": "group_1000_bot_def456",
        "name": "Reviewate",
        "bot": True,
    }
    mock_get_token_type.return_value = GitlabTokenType.GROUP_ACCESS_TOKEN
    mock_fetch_group.return_value = {
        "id": 1000,
        "name": "Root Group",
        "path": "root-group",
        "parent_id": None,
    }
    mock_determine_role.return_value = "admin"

    response = authenticated_client.post(
        "/sources/gitlab",
        json={"access_token": "glpat-root-token"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["source_type"] == "group"
    assert data["source_id"] == str(existing_org.id)

    # Org should now have the token
    db_session.refresh(existing_org)
    assert existing_org.gitlab_access_token_encrypted is not None


# =============================================================================
# resolve_root_group Tests
# =============================================================================


@pytest.mark.asyncio
async def test_resolve_root_group_no_parent():
    """Test resolve_root_group returns the group itself when no parent."""
    config = GitLabPluginConfig(
        enabled=True,
        oauth=GitLabOAuthConfig(client_id="test", client_secret="test"),
    )
    plugin = GitLabPlugin(plugin_config=config)

    with patch.object(plugin, "fetch_group", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = {"id": 100, "name": "Root", "parent_id": None}
        result = await plugin.resolve_root_group("token", "100")

    assert result["id"] == 100
    mock_fetch.assert_called_once_with("token", "100")


@pytest.mark.asyncio
async def test_resolve_root_group_one_level():
    """Test resolve_root_group walks up one parent level."""
    config = GitLabPluginConfig(
        enabled=True,
        oauth=GitLabOAuthConfig(client_id="test", client_secret="test"),
    )
    plugin = GitLabPlugin(plugin_config=config)

    with patch.object(plugin, "fetch_group", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.side_effect = [
            {"id": 200, "name": "Child", "parent_id": 100},
            {"id": 100, "name": "Root", "parent_id": None},
        ]
        result = await plugin.resolve_root_group("token", "200")

    assert result["id"] == 100
    assert mock_fetch.call_count == 2


@pytest.mark.asyncio
async def test_resolve_root_group_403_fallback():
    """Test resolve_root_group stops at highest accessible group on 403."""
    config = GitLabPluginConfig(
        enabled=True,
        oauth=GitLabOAuthConfig(client_id="test", client_secret="test"),
    )
    plugin = GitLabPlugin(plugin_config=config)

    with patch.object(plugin, "fetch_group", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.side_effect = [
            {"id": 200, "name": "Subgroup", "parent_id": 100},
            HTTPException(status_code=500, detail="403"),
        ]
        result = await plugin.resolve_root_group("token", "200")

    assert result["id"] == 200
    assert result["name"] == "Subgroup"
