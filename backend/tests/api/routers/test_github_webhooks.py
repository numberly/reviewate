"""Tests for GitHub webhook endpoints and consumers."""

from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.database import (
    db_get_pull_request_by_pr_number,
    db_get_repository_by_external_id,
)
from api.models import Organization, PullRequest, Repository, User
from api.routers.webhooks.github import consumer
from api.routers.webhooks.github.schemas import (
    GitHubSyncInstallationMessage,
    GitHubSyncRepositoryPRsMessage,
)
from tests.utils.factories import ProviderIdentityFactory, PullRequestFactory, RepositoryFactory

# =============================================================================
# Webhook Handler Tests
# =============================================================================


@patch("api.sse.publishers.get_faststream_broker")
@patch("api.routers.webhooks.github.installations.get_faststream_broker")
def test_installation_created_webhook_queues_sync(
    mock_get_broker_handler,
    mock_get_broker_sse,
    client: TestClient,
    create_user: User,
    db_session: Session,
    mock_github_app_private_key,
):
    """Test that installation.created webhook creates org and queues sync job."""
    # Setup mocks
    mock_broker = MagicMock()
    mock_broker.publish = AsyncMock(return_value=None)
    mock_get_broker_handler.return_value = mock_broker
    mock_get_broker_sse.return_value = mock_broker

    # Setup user with provider identity (github_external_id is now in ProviderIdentity)
    identity = ProviderIdentityFactory.build(
        provider="github",
        external_id="999",
        user_id=create_user.id,
    )
    db_session.add(identity)
    db_session.commit()

    # Prepare webhook payload
    webhook_payload = {
        "action": "created",
        "installation": {
            "id": 12345678,
            "account": {
                "id": 98765,
                "login": "test-org",
                "type": "Organization",
            },
        },
        "sender": {
            "id": 999,
            "login": "sender",
        },
    }

    # Send webhook
    response = client.post(
        "/webhooks/github",
        json=webhook_payload,
        headers={
            "x-github-event": "installation",
            "x-hub-signature-256": "sha256=fake_signature",
        },
    )

    # Verify response
    assert response.status_code == 202
    data = response.json()
    assert data["processed"] is True
    assert "syncing repositories" in data["message"] and "in background" in data["message"]

    # Verify organization was created
    org = db_session.query(Organization).filter(Organization.installation_id == "12345678").first()
    assert org is not None
    assert org.name == "test-org"

    # Verify events were published (SSE organization event + repo sync job + member sync job)
    assert mock_broker.publish.call_count == 3

    # First call should be SSE organization event
    first_call = mock_broker.publish.call_args_list[0]
    org_event = first_call[0][0]
    org_channel = first_call[1]["channel"]
    assert org_channel == "reviewate.events.organizations"
    assert org_event.user_id == str(create_user.id)
    assert org_event.action == "created"

    # Second call should be sync job (stream-based)
    second_call = mock_broker.publish.call_args_list[1]
    event_data = second_call[0][0]
    assert event_data.installation_id == "12345678"
    assert event_data.sender_github_id == "999"
    assert second_call[1]["stream"] == "reviewate.events.github.sync_installation"


def test_pull_request_webhook_creates_pr(
    client: TestClient,
    create_organization: Organization,
    db_session: Session,
):
    """Test that pull_request webhook creates PR record."""

    # Create repository using factory
    repo = RepositoryFactory.build(
        organization_id=create_organization.id,
        external_repo_id="repo123",
        name="test-repo",
        web_url="https://github.com/test-org/test-repo",
        provider="github",
        provider_url="https://github.com",
    )
    db_session.add(repo)
    db_session.commit()

    # Prepare webhook payload
    webhook_payload = {
        "action": "opened",
        "number": 1,
        "pull_request": {
            "id": 456789,
            "title": "Test PR",
            "state": "open",
            "user": {"login": "testuser"},
            "head": {"ref": "feature-branch", "sha": "abc123"},
            "base": {"ref": "main"},
            "html_url": "https://github.com/test-org/test-repo/pull/1",
        },
        "repository": {
            "id": 123,  # Different from external_repo_id to test conversion
            "name": "test-repo",
        },
        "sender": {"login": "testuser"},
    }

    # Update repo external_id to match payload
    repo.external_repo_id = "123"
    db_session.commit()

    # Send webhook
    response = client.post(
        "/webhooks/github",
        json=webhook_payload,
        headers={
            "x-github-event": "pull_request",
            "x-hub-signature-256": "sha256=fake_signature",
        },
    )

    # Verify response
    assert response.status_code == 202
    data = response.json()
    assert data["processed"] is True
    assert "Pull request #1 created successfully" in data["message"]

    # Verify PR was created
    pr = db_get_pull_request_by_pr_number(db_session, str(repo.id), 1)
    assert pr is not None
    assert pr.title == "Test PR"
    assert pr.author == "testuser"
    assert pr.head_sha == "abc123"


@patch("api.routers.webhooks.utils.get_faststream_broker")
def test_label_trigger_skipped_when_execution_active(
    mock_get_broker,
    client: TestClient,
    create_organization: Organization,
    db_session: Session,
):
    """Test that label trigger is skipped if an active execution already exists."""
    from api.database import db_create_execution, db_upsert_pull_request

    mock_broker = MagicMock()
    mock_broker.publish = AsyncMock(return_value=None)
    mock_get_broker.return_value = mock_broker

    # Set org to use label trigger
    create_organization.automatic_review_trigger = "label"
    db_session.commit()

    # Create repository
    repo = RepositoryFactory.build(
        organization_id=create_organization.id,
        external_repo_id="123",
        name="test-repo",
        web_url="https://github.com/test-org/test-repo",
        provider="github",
        provider_url="https://github.com",
    )
    db_session.add(repo)
    db_session.commit()

    # Create PR
    pr, _ = db_upsert_pull_request(
        db=db_session,
        organization_id=create_organization.id,
        repository_id=repo.id,
        pr_number=1,
        external_pr_id="456789",
        title="Test PR",
        author="testuser",
        state="open",
        head_branch="feature-branch",
        base_branch="main",
        head_sha="abc123",
        pr_url="https://github.com/test-org/test-repo/pull/1",
    )

    # Create an active execution (queued) for this PR
    db_create_execution(
        db=db_session,
        organization_id=create_organization.id,
        repository_id=repo.id,
        pull_request_id=pr.id,
        pr_number=1,
        commit_sha="abc123",
        status="queued",
        workflow="review",
    )

    # Send labeled webhook
    webhook_payload = {
        "action": "labeled",
        "number": 1,
        "pull_request": {
            "id": 456789,
            "title": "Test PR",
            "state": "open",
            "user": {"login": "testuser"},
            "head": {"ref": "feature-branch", "sha": "abc123"},
            "base": {"ref": "main"},
            "html_url": "https://github.com/test-org/test-repo/pull/1",
        },
        "label": {"name": "reviewate"},
        "repository": {"id": 123, "name": "test-repo"},
        "sender": {"login": "testuser"},
    }

    response = client.post(
        "/webhooks/github",
        json=webhook_payload,
        headers={
            "x-github-event": "pull_request",
            "x-hub-signature-256": "sha256=fake_signature",
        },
    )

    assert response.status_code == 202
    data = response.json()
    assert data["processed"] is False
    assert "already running" in data["message"]

    # Verify no job was published (broker.publish should NOT be called for the job)
    mock_broker.publish.assert_not_called()


# =============================================================================
# Consumer Tests
# =============================================================================


@pytest.mark.asyncio
@patch("api.sse.publishers.get_faststream_broker")
@patch("api.routers.webhooks.github.consumer.get_faststream_broker")
@patch("api.routers.webhooks.github.consumer.get_current_app")
async def test_sync_installation_repositories_consumer(
    mock_get_app,
    mock_get_broker_consumer,
    mock_get_broker_sse,
    db_session: Session,
    create_organization: Organization,
):
    """Test sync_installation_repositories consumer syncs repos and queues PR sync."""
    # Update org with installation_id
    create_organization.installation_id = "install123"
    db_session.commit()

    # Mock GitHub plugin
    mock_repos = [
        {
            "id": 111,
            "name": "repo1",
            "html_url": "https://github.com/org/repo1",
            "owner": {"login": "test-org"},
        },
        {
            "id": 222,
            "name": "repo2",
            "html_url": "https://github.com/org/repo2",
            "owner": {"login": "test-org"},
        },
    ]

    # Setup mocks
    mock_app = MagicMock()
    mock_github = AsyncMock()
    mock_github.get_installation_access_token.return_value = "token123"
    mock_github.fetch_installation_repositories.return_value = mock_repos
    mock_app.github = mock_github
    mock_get_app.return_value = mock_app

    # Mock database session context manager
    @contextmanager
    def _session():
        yield db_session

    mock_app.database.session = _session

    # Mock broker
    mock_broker = MagicMock()
    mock_broker.publish = AsyncMock(return_value=None)
    mock_get_broker_consumer.return_value = mock_broker
    mock_get_broker_sse.return_value = mock_broker

    # Call consumer
    message = GitHubSyncInstallationMessage(installation_id="install123", sender_github_id="999")
    await consumer.sync_installation_repositories(message)

    # Verify repos were created
    repo1 = db_get_repository_by_external_id(db_session, "111")
    assert repo1 is not None
    assert repo1.name == "repo1"

    repo2 = db_get_repository_by_external_id(db_session, "222")
    assert repo2 is not None
    assert repo2.name == "repo2"

    # Verify events were published (2 SSE repo events + 2 PR sync jobs = 4 total)
    assert mock_broker.publish.call_count == 4


@pytest.mark.asyncio
@patch("api.routers.webhooks.github.consumer.get_current_app")
async def test_sync_repository_pull_requests_consumer(
    mock_get_app,
    db_session: Session,
    create_organization: Organization,
):
    """Test sync_repository_pull_requests consumer syncs PRs."""
    # Create repository using factory
    repo = RepositoryFactory.build(
        organization_id=create_organization.id,
        external_repo_id="repo123",
        name="test-repo",
        web_url="https://github.com/test-org/test-repo",
        provider="github",
        provider_url="https://github.com",
    )
    db_session.add(repo)
    db_session.commit()

    # Mock GitHub API PRs response
    mock_prs = [
        {
            "id": 1001,
            "number": 1,
            "title": "PR 1",
            "state": "open",
            "user": {"login": "user1"},
            "head": {"ref": "feature1", "sha": "sha1"},
            "base": {"ref": "main", "repo": {"id": 123}},
            "html_url": "https://github.com/org/repo/pull/1",
        },
        {
            "id": 1002,
            "number": 2,
            "title": "PR 2",
            "state": "open",
            "user": {"login": "user2"},
            "head": {"ref": "feature2", "sha": "sha2"},
            "base": {"ref": "main", "repo": {"id": 123}},
            "html_url": "https://github.com/org/repo/pull/2",
        },
    ]

    # Setup mocks
    mock_app = MagicMock()
    mock_github = AsyncMock()
    mock_github.get_installation_access_token.return_value = "token123"
    mock_github.list_pull_requests.return_value = mock_prs
    mock_app.github = mock_github
    mock_get_app.return_value = mock_app

    # Mock database session context manager
    @contextmanager
    def _session():
        yield db_session

    mock_app.database.session = _session

    # Update repo external_id to match mock PR base repo id
    repo.external_repo_id = "123"
    db_session.commit()

    # Store repo ID before consumer call (to avoid detached instance error)
    repo_id = repo.id

    # Call consumer
    message = GitHubSyncRepositoryPRsMessage(
        repository_id=str(repo_id),
        installation_id="install123",
        owner="test-org",
        repo_name="test-repo",
    )
    await consumer.sync_repository_pull_requests(message)

    # Verify PRs were created
    pr1 = db_get_pull_request_by_pr_number(db_session, str(repo_id), 1)
    assert pr1 is not None
    assert pr1.title == "PR 1"
    assert pr1.author == "user1"

    pr2 = db_get_pull_request_by_pr_number(db_session, str(repo_id), 2)
    assert pr2 is not None
    assert pr2.title == "PR 2"
    assert pr2.author == "user2"


@pytest.mark.asyncio
@patch("api.routers.webhooks.github.consumer.get_current_app")
async def test_sync_installation_skips_existing_repos(
    mock_get_app,
    db_session: Session,
    create_organization: Organization,
):
    """Test that sync_installation_repositories skips already existing repos."""
    # Update org with installation_id
    create_organization.installation_id = "install123"
    db_session.commit()

    # Create existing repository using factory
    existing_repo = RepositoryFactory.build(
        organization_id=create_organization.id,
        external_repo_id="111",
        name="existing-repo",
        web_url="https://github.com/org/repo1",
        provider="github",
        provider_url="https://github.com",
    )
    db_session.add(existing_repo)
    db_session.commit()

    # Mock GitHub plugin (same repo ID as existing)
    mock_repos = [
        {
            "id": 111,  # Same as existing
            "name": "repo1",
            "html_url": "https://github.com/org/repo1",
            "owner": {"login": "test-org"},
        },
    ]

    # Setup mocks
    mock_app = MagicMock()
    mock_github = AsyncMock()
    mock_github.get_installation_access_token.return_value = "token123"
    mock_github.fetch_installation_repositories.return_value = mock_repos
    mock_app.github = mock_github
    mock_get_app.return_value = mock_app

    # Mock database session context manager
    @contextmanager
    def _session():
        yield db_session

    mock_app.database.session = _session

    # Call consumer
    message = GitHubSyncInstallationMessage(installation_id="install123", sender_github_id="999")
    await consumer.sync_installation_repositories(message)

    # Verify no new repo was created (still only 1)
    repos = (
        db_session.query(Repository)
        .filter(Repository.organization_id == create_organization.id)
        .all()
    )
    assert len(repos) == 1
    assert repos[0].id == existing_repo.id


@pytest.mark.asyncio
@patch("api.routers.webhooks.github.consumer.get_current_app")
async def test_sync_prs_skips_existing_prs(
    mock_get_app,
    db_session: Session,
    create_organization: Organization,
):
    """Test that sync_repository_pull_requests skips already existing PRs."""
    # Create repository using factory
    repo = RepositoryFactory.build(
        organization_id=create_organization.id,
        external_repo_id="123",
        name="test-repo",
        web_url="https://github.com/test-org/test-repo",
        provider="github",
        provider_url="https://github.com",
    )
    db_session.add(repo)
    db_session.commit()

    # Create existing PR using factory
    existing_pr = PullRequestFactory.build(
        organization_id=create_organization.id,
        repository_id=repo.id,
        pr_number=1,
        external_pr_id="1001",
        title="Existing PR",
        author="user1",
        state="open",
        head_branch="feature1",
        base_branch="main",
        head_sha="sha1",
        pr_url="https://github.com/org/repo/pull/1",
    )
    db_session.add(existing_pr)
    db_session.commit()

    # Mock GitHub API (same PR as existing)
    mock_prs = [
        {
            "id": 1001,  # Same as existing
            "number": 1,
            "title": "PR 1",
            "state": "open",
            "user": {"login": "user1"},
            "head": {"ref": "feature1", "sha": "sha1"},
            "base": {"ref": "main", "repo": {"id": 123}},
            "html_url": "https://github.com/org/repo/pull/1",
        },
    ]

    # Setup mocks
    mock_app = MagicMock()
    mock_github = AsyncMock()
    mock_github.get_installation_access_token.return_value = "token123"
    mock_github.list_pull_requests.return_value = mock_prs
    mock_app.github = mock_github
    mock_get_app.return_value = mock_app

    # Mock database session context manager
    @contextmanager
    def _session():
        yield db_session

    mock_app.database.session = _session

    # Call consumer
    message = GitHubSyncRepositoryPRsMessage(
        repository_id=str(repo.id),
        installation_id="install123",
        owner="test-org",
        repo_name="test-repo",
    )
    await consumer.sync_repository_pull_requests(message)

    # Verify no new PR was created (still only 1)
    prs = db_session.query(PullRequest).filter(PullRequest.repository_id == repo.id).all()
    assert len(prs) == 1
    assert prs[0].id == existing_pr.id
