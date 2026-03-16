"""Tests for auth sync consumer."""

from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from api.app import Application
from api.models import OrganizationMembership, RepositoryMembership
from api.routers.auth.consumer import (
    _sync_github_memberships,
    _sync_gitlab_memberships,
    sync_user_memberships,
)
from api.routers.auth.schemas import SyncUserMembershipsMessage
from tests.utils.factories import (
    OrganizationFactory,
    ProviderIdentityFactory,
    RepositoryFactory,
    UserFactory,
)

# =============================================================================
# sync_user_memberships Tests
# =============================================================================


@pytest.mark.asyncio
@patch("api.routers.auth.consumer.get_current_app")
@patch("api.routers.auth.consumer.get_encryptor")
@patch("api.routers.auth.consumer._sync_github_memberships")
async def test_sync_user_memberships_github_success(
    mock_sync_github: AsyncMock,
    mock_get_encryptor: MagicMock,
    mock_get_app: MagicMock,
    db_session: Session,
):
    """Test that GitHub sync is called with correct parameters."""
    # Setup - create user and provider identity
    user = UserFactory.build()
    db_session.add(user)
    db_session.commit()

    identity = ProviderIdentityFactory.build(
        provider="github",
        external_id="12345",
        user_id=user.id,
    )
    db_session.add(identity)
    db_session.commit()

    mock_get_encryptor.return_value.decrypt.return_value = "decrypted_token"
    mock_get_app.return_value = MagicMock()
    mock_sync_github.return_value = None

    message = SyncUserMembershipsMessage(
        user_id=str(user.id),
        provider="github",
        access_token_encrypted="encrypted_token",
        external_user_id="12345",
        username="testuser",
    )

    # Execute
    await sync_user_memberships(message)

    # Verify
    mock_sync_github.assert_called_once()
    call_args = mock_sync_github.call_args
    # New signature: (app, provider_identity_id, user_uuid, access_token)
    assert call_args[0][2] == user.id  # user_uuid
    assert call_args[0][3] == "decrypted_token"  # access_token


@pytest.mark.asyncio
@patch("api.routers.auth.consumer.get_current_app")
@patch("api.routers.auth.consumer.get_encryptor")
@patch("api.routers.auth.consumer._sync_gitlab_memberships")
async def test_sync_user_memberships_gitlab_success(
    mock_sync_gitlab: AsyncMock,
    mock_get_encryptor: MagicMock,
    mock_get_app: MagicMock,
    db_session: Session,
):
    """Test that GitLab sync is called with correct parameters."""
    # Setup - create user and provider identity
    user = UserFactory.build()
    db_session.add(user)
    db_session.commit()

    identity = ProviderIdentityFactory.build(
        provider="gitlab",
        external_id="54321",
        user_id=user.id,
    )
    db_session.add(identity)
    db_session.commit()

    mock_get_encryptor.return_value.decrypt.return_value = "decrypted_token"
    mock_get_app.return_value = MagicMock()
    mock_sync_gitlab.return_value = None

    message = SyncUserMembershipsMessage(
        user_id=str(user.id),
        provider="gitlab",
        access_token_encrypted="encrypted_token",
        external_user_id="54321",
        username="gitlabuser",
    )

    # Execute
    await sync_user_memberships(message)

    # Verify
    mock_sync_gitlab.assert_called_once()
    call_args = mock_sync_gitlab.call_args
    # New signature: (app, provider_identity_id, user_uuid, access_token, external_user_id)
    assert call_args[0][2] == user.id  # user_uuid
    assert call_args[0][3] == "decrypted_token"  # access_token
    assert call_args[0][4] == "54321"  # external_user_id


@pytest.mark.asyncio
@patch("api.routers.auth.consumer.get_current_app")
@patch("api.routers.auth.consumer.get_encryptor")
async def test_sync_user_memberships_decryption_failure(
    mock_get_encryptor: MagicMock,
    mock_get_app: MagicMock,
):
    """Test that decryption failure is handled gracefully."""
    # Setup - encryptor raises exception
    mock_get_encryptor.return_value.decrypt.side_effect = Exception("Decryption failed")
    mock_get_app.return_value = MagicMock()

    message = SyncUserMembershipsMessage(
        user_id=str(uuid4()),
        provider="github",
        access_token_encrypted="bad_encrypted_token",
        external_user_id="12345",
        username="testuser",
    )

    # Execute - should not raise
    await sync_user_memberships(message)

    # Verify - database session should not be used since we returned early
    mock_get_app.return_value.database.session.assert_not_called()


# =============================================================================
# _sync_github_memberships Tests
# =============================================================================


@pytest.mark.asyncio
async def test_sync_github_no_installations(db_session: Session, test_app: Application):
    """Test GitHub sync when user has no accessible installations."""
    # Setup - create user and provider identity
    user = UserFactory.build()
    db_session.add(user)
    db_session.commit()

    identity = ProviderIdentityFactory.build(
        provider="github",
        external_id="12345",
        user_id=user.id,
    )
    db_session.add(identity)
    db_session.commit()

    # Patch the GitHub plugin method on test_app
    with patch.object(
        test_app.github, "fetch_user_installations", new_callable=AsyncMock, return_value=[]
    ):
        # Execute - should complete without error (no DB session opened)
        await _sync_github_memberships(
            app=test_app,
            provider_identity_id=identity.id,
            user_id=user.id,
            access_token="test_token",
        )

    # Verify - no memberships created
    memberships = (
        db_session.query(OrganizationMembership).filter_by(provider_identity_id=identity.id).all()
    )
    assert len(memberships) == 0


@pytest.mark.asyncio
async def test_sync_github_creates_memberships(db_session: Session, test_app: Application):
    """Test GitHub sync creates org and repo memberships."""
    # Setup - create user with identity, org, and repo
    user = UserFactory.build()
    org = OrganizationFactory.build(
        installation_id="123",
        provider="github",
        external_org_id="org-456",
    )
    repo = RepositoryFactory.build(
        organization_id=org.id,
        provider="github",
    )
    db_session.add_all([user, org, repo])
    db_session.commit()

    identity = ProviderIdentityFactory.build(
        provider="github",
        external_id="12345",
        user_id=user.id,
    )
    db_session.add(identity)
    db_session.commit()

    @contextmanager
    def _session():
        yield db_session

    # Patch GitHub plugin methods on test_app and database session
    with (
        patch.object(
            test_app.github,
            "fetch_user_installations",
            new_callable=AsyncMock,
            return_value=[{"id": 123, "account": {"login": "test-org"}}],
        ),
        patch.object(
            test_app.github,
            "get_user_org_membership",
            new_callable=AsyncMock,
            return_value="admin",
        ),
        patch.object(test_app.database, "session", _session),
    ):
        await _sync_github_memberships(
            app=test_app,
            provider_identity_id=identity.id,
            user_id=user.id,
            access_token="test_token",
        )

    # Verify - org membership created with provider_identity_id
    org_membership = (
        db_session.query(OrganizationMembership)
        .filter_by(provider_identity_id=identity.id, organization_id=org.id)
        .first()
    )
    assert org_membership is not None
    assert org_membership.role == "admin"

    # Verify - repo membership created with user_id
    repo_membership = (
        db_session.query(RepositoryMembership)
        .filter_by(user_id=user.id, repository_id=repo.id)
        .first()
    )
    assert repo_membership is not None
    assert repo_membership.role == "admin"


@pytest.mark.asyncio
async def test_sync_github_plugin_not_available(db_session: Session):
    """Test GitHub sync when plugin is not available.

    Note: Using MagicMock here because test_app always has github plugin.
    This tests edge case where plugin is disabled/unavailable.
    """
    user = UserFactory.build()
    db_session.add(user)
    db_session.commit()

    identity = ProviderIdentityFactory.build(
        provider="github",
        external_id="12345",
        user_id=user.id,
    )
    db_session.add(identity)
    db_session.commit()

    # Mock app with github=None to simulate plugin not available
    mock_app = MagicMock(spec=Application)
    mock_app.github = None

    # Execute - should complete without error
    await _sync_github_memberships(
        app=mock_app,
        provider_identity_id=identity.id,
        user_id=user.id,
        access_token="test_token",
    )

    # Verify - no memberships created
    memberships = (
        db_session.query(OrganizationMembership).filter_by(provider_identity_id=identity.id).all()
    )
    assert len(memberships) == 0


# =============================================================================
# _sync_gitlab_memberships Tests
# =============================================================================


@pytest.mark.asyncio
async def test_sync_gitlab_personal_namespace_as_admin(db_session: Session, test_app: Application):
    """Test GitLab sync marks personal namespace membership as admin."""
    # Setup - create user with identity and personal namespace org
    user = UserFactory.build()
    org = OrganizationFactory.build(
        external_org_id="789",
        provider="gitlab",
        name="testuser",
    )
    db_session.add_all([user, org])
    db_session.commit()

    identity = ProviderIdentityFactory.build(
        provider="gitlab",
        external_id="12345",
        user_id=user.id,
    )
    db_session.add(identity)
    db_session.commit()

    @contextmanager
    def _session():
        yield db_session

    # Patch GitLab plugin methods on test_app and database session
    with (
        patch.object(test_app.gitlab, "fetch_user_groups", new_callable=AsyncMock, return_value=[]),
        patch.object(
            test_app.gitlab,
            "fetch_user_namespaces",
            new_callable=AsyncMock,
            return_value=[{"id": 789, "name": "testuser", "path": "testuser", "kind": "user"}],
        ),
        patch.object(test_app.database, "session", _session),
    ):
        await _sync_gitlab_memberships(
            app=test_app,
            provider_identity_id=identity.id,
            user_id=user.id,
            access_token="test_token",
            external_user_id="12345",
        )

    # Verify - org membership created with admin role
    org_membership = (
        db_session.query(OrganizationMembership)
        .filter_by(provider_identity_id=identity.id, organization_id=org.id)
        .first()
    )
    assert org_membership is not None
    assert org_membership.role == "admin"  # Personal namespace = admin


@pytest.mark.asyncio
async def test_sync_gitlab_group_with_role(db_session: Session, test_app: Application):
    """Test GitLab sync creates membership with correct role from API."""
    # Setup - create user with identity
    user = UserFactory.build()
    org = OrganizationFactory.build(
        external_org_id="456",
        provider="gitlab",
        name="test-group",
    )
    db_session.add_all([user, org])
    db_session.commit()

    identity = ProviderIdentityFactory.build(
        provider="gitlab",
        external_id="12345",
        user_id=user.id,
    )
    db_session.add(identity)
    db_session.commit()

    @contextmanager
    def _session():
        yield db_session

    # Patch GitLab plugin methods on test_app and database session
    with (
        patch.object(
            test_app.gitlab, "fetch_user_namespaces", new_callable=AsyncMock, return_value=[]
        ),
        patch.object(
            test_app.gitlab,
            "fetch_user_groups",
            new_callable=AsyncMock,
            return_value=[{"id": 456, "name": "test-group"}],
        ),
        patch.object(
            test_app.gitlab,
            "determine_user_role_in_group",
            new_callable=AsyncMock,
            return_value="member",
        ),
        patch.object(test_app.database, "session", _session),
    ):
        await _sync_gitlab_memberships(
            app=test_app,
            provider_identity_id=identity.id,
            user_id=user.id,
            access_token="test_token",
            external_user_id="12345",
        )

    # Verify
    org_membership = (
        db_session.query(OrganizationMembership)
        .filter_by(provider_identity_id=identity.id, organization_id=org.id)
        .first()
    )
    assert org_membership is not None
    assert org_membership.role == "member"


@pytest.mark.asyncio
async def test_sync_gitlab_plugin_not_available(db_session: Session):
    """Test GitLab sync when plugin is not available.

    Note: Using MagicMock here because test_app always has gitlab plugin.
    This tests edge case where plugin is disabled/unavailable.
    """
    user = UserFactory.build()
    db_session.add(user)
    db_session.commit()

    identity = ProviderIdentityFactory.build(
        provider="gitlab",
        external_id="12345",
        user_id=user.id,
    )
    db_session.add(identity)
    db_session.commit()

    # Mock app with gitlab=None to simulate plugin not available
    mock_app = MagicMock(spec=Application)
    mock_app.gitlab = None

    # Execute - should complete without error
    await _sync_gitlab_memberships(
        app=mock_app,
        provider_identity_id=identity.id,
        user_id=user.id,
        access_token="test_token",
        external_user_id="12345",
    )

    # Verify - no memberships created
    memberships = (
        db_session.query(OrganizationMembership).filter_by(provider_identity_id=identity.id).all()
    )
    assert len(memberships) == 0


@pytest.mark.asyncio
async def test_sync_gitlab_org_not_in_db(db_session: Session, test_app: Application):
    """Test GitLab sync skips groups not in our database."""
    # Setup - user with identity exists but no matching org
    user = UserFactory.build()
    db_session.add(user)
    db_session.commit()

    identity = ProviderIdentityFactory.build(
        provider="gitlab",
        external_id="12345",
        user_id=user.id,
    )
    db_session.add(identity)
    db_session.commit()

    @contextmanager
    def _session():
        yield db_session

    # Patch GitLab plugin methods on test_app and database session
    with (
        patch.object(
            test_app.gitlab, "fetch_user_namespaces", new_callable=AsyncMock, return_value=[]
        ),
        patch.object(
            test_app.gitlab,
            "fetch_user_groups",
            new_callable=AsyncMock,
            return_value=[{"id": 999, "name": "unknown-group"}],  # No matching org in DB
        ),
        patch.object(test_app.database, "session", _session),
    ):
        await _sync_gitlab_memberships(
            app=test_app,
            provider_identity_id=identity.id,
            user_id=user.id,
            access_token="test_token",
            external_user_id="12345",
        )

    # Verify - no memberships created
    memberships = (
        db_session.query(OrganizationMembership).filter_by(provider_identity_id=identity.id).all()
    )
    assert len(memberships) == 0
