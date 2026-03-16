"""Tests for pull request endpoints."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.database import (
    db_create_execution,
    db_create_pull_request,
    db_create_repository,
    db_get_user_identities,
)
from api.models import Organization, OrganizationMembership, User


def test_list_repository_pull_requests(
    authenticated_client: TestClient,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
    db_session: Session,
):
    """Test listing pull requests for a repository."""
    _user, org, _membership = user_with_organization

    # Create repository
    repository = db_create_repository(
        db=db_session,
        organization_id=org.id,
        external_repo_id="12345",
        name="test-repo",
        web_url="https://github.com/test/repo",
        provider="github",
        provider_url="https://github.com",
    )

    # Create pull requests
    pr1 = db_create_pull_request(
        db=db_session,
        organization_id=org.id,
        repository_id=repository.id,
        pr_number=1,
        external_pr_id="pr-1",
        title="First PR",
        author="user1",
        state="opened",
        head_branch="feature-1",
        base_branch="main",
        head_sha="abc123",
        pr_url="https://github.com/test/repo/pull/1",
    )

    _pr2 = db_create_pull_request(
        db=db_session,
        organization_id=org.id,
        repository_id=repository.id,
        pr_number=2,
        external_pr_id="pr-2",
        title="Second PR",
        author="user2",
        state="merged",
        head_branch="feature-2",
        base_branch="main",
        head_sha="abc123",
        pr_url="https://github.com/test/repo/pull/2",
    )

    # Create execution for pr1
    execution = db_create_execution(
        db=db_session,
        organization_id=org.id,
        repository_id=repository.id,
        pull_request_id=pr1.id,
        pr_number=1,
        commit_sha="abc1234",
        status="completed",
    )
    db_session.commit()

    # List pull requests
    response = authenticated_client.get(f"/repositories/{repository.id}/pull-requests")

    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert "objects" in data
    assert len(data["objects"]) == 2

    # Verify PR details
    prs = {pr["pr_number"]: pr for pr in data["objects"]}
    assert 1 in prs
    assert 2 in prs

    # Verify PR1 has execution
    assert prs[1]["title"] == "First PR"
    assert prs[1]["latest_execution_id"] == str(execution.id)
    assert prs[1]["latest_execution_status"] == "completed"

    # Verify PR2 has no execution
    assert prs[2]["title"] == "Second PR"
    assert prs[2]["latest_execution_id"] is None
    assert prs[2]["latest_execution_status"] is None


def test_list_repository_pull_requests_empty(
    authenticated_client: TestClient,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
    db_session: Session,
):
    """Test listing pull requests for a repository with no PRs."""
    _user, org, _membership = user_with_organization

    # Create repository
    repository = db_create_repository(
        db=db_session,
        organization_id=org.id,
        external_repo_id="12345",
        name="test-repo",
        web_url="https://github.com/test/repo",
        provider="github",
        provider_url="https://github.com",
    )
    db_session.commit()

    # List pull requests
    response = authenticated_client.get(f"/repositories/{repository.id}/pull-requests")

    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["objects"] == []


def test_list_repository_pull_requests_requires_authentication(
    client: TestClient,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
    db_session: Session,
):
    """Test that listing pull requests requires authentication."""
    _user, org, _membership = user_with_organization

    # Create repository
    repository = db_create_repository(
        db=db_session,
        organization_id=org.id,
        external_repo_id="12345",
        name="test-repo",
        web_url="https://github.com/test/repo",
        provider="github",
        provider_url="https://github.com",
    )
    db_session.commit()

    # Try without auth
    response = client.get(f"/repositories/{repository.id}/pull-requests")

    # Verify error
    assert response.status_code == 401


def test_list_repository_pull_requests_requires_membership(
    authenticated_client: TestClient,
    create_user: User,
    create_organization: Organization,
    db_session: Session,
):
    """Test that listing pull requests requires organization membership."""
    # Create repository in organization where user is not a member
    repository = db_create_repository(
        db=db_session,
        organization_id=create_organization.id,
        external_repo_id="12345",
        name="test-repo",
        web_url="https://github.com/test/repo",
        provider="github",
        provider_url="https://github.com",
    )
    db_session.commit()

    # Try to list PRs
    response = authenticated_client.get(f"/repositories/{repository.id}/pull-requests")

    # Verify error (message from auth dependency verify_repository_access)
    assert response.status_code == 403
    assert "don't have access to this repository" in response.json()["detail"]


def test_list_repository_pull_requests_invalid_id(
    authenticated_client: TestClient,
):
    """Test that invalid repository ID returns 400."""
    response = authenticated_client.get("/repositories/not-a-uuid/pull-requests")

    assert response.status_code == 400
    assert "Invalid repository ID format" in response.json()["detail"]


def test_list_repository_pull_requests_not_found(
    authenticated_client: TestClient,
):
    """Test that non-existent repository returns 404."""
    fake_id = uuid4()
    response = authenticated_client.get(f"/repositories/{fake_id}/pull-requests")

    assert response.status_code == 404
    assert "Repository not found" in response.json()["detail"]


def test_get_pull_request(
    authenticated_client: TestClient,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
    db_session: Session,
):
    """Test getting a single pull request."""
    _user, org, _membership = user_with_organization

    # Create repository
    repository = db_create_repository(
        db=db_session,
        organization_id=org.id,
        external_repo_id="12345",
        name="test-repo",
        web_url="https://github.com/test/repo",
        provider="github",
        provider_url="https://github.com",
    )

    # Create pull request
    pr = db_create_pull_request(
        db=db_session,
        organization_id=org.id,
        repository_id=repository.id,
        pr_number=42,
        external_pr_id="pr-42",
        title="Test PR",
        author="testuser",
        state="opened",
        head_branch="feature",
        base_branch="main",
        head_sha="abc123",
        pr_url="https://github.com/test/repo/pull/42",
    )
    db_session.commit()

    # Get pull request
    response = authenticated_client.get(f"/pull-requests/{pr.id}")

    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(pr.id)
    assert data["pr_number"] == 42
    assert data["title"] == "Test PR"
    assert data["author"] == "testuser"
    assert data["state"] == "opened"
    assert data["head_branch"] == "feature"
    assert data["base_branch"] == "main"


def test_get_pull_request_requires_authentication(
    client: TestClient,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
    db_session: Session,
):
    """Test that getting a pull request requires authentication."""
    _user, org, _membership = user_with_organization

    # Create repository and PR
    repository = db_create_repository(
        db=db_session,
        organization_id=org.id,
        external_repo_id="12345",
        name="test-repo",
        web_url="https://github.com/test/repo",
        provider="github",
        provider_url="https://github.com",
    )

    pr = db_create_pull_request(
        db=db_session,
        organization_id=org.id,
        repository_id=repository.id,
        pr_number=42,
        external_pr_id="pr-42",
        title="Test PR",
        author="testuser",
        state="opened",
        head_branch="feature",
        base_branch="main",
        head_sha="abc123",
        pr_url="https://github.com/test/repo/pull/42",
    )
    db_session.commit()

    # Try without auth
    response = client.get(f"/pull-requests/{pr.id}")

    # Verify error
    assert response.status_code == 401


def test_get_pull_request_requires_membership(
    authenticated_client: TestClient,
    create_user: User,
    create_organization: Organization,
    db_session: Session,
):
    """Test that getting a pull request requires organization membership."""
    # Create repository and PR in organization where user is not a member
    repository = db_create_repository(
        db=db_session,
        organization_id=create_organization.id,
        external_repo_id="12345",
        name="test-repo",
        web_url="https://github.com/test/repo",
        provider="github",
        provider_url="https://github.com",
    )

    pr = db_create_pull_request(
        db=db_session,
        organization_id=create_organization.id,
        repository_id=repository.id,
        pr_number=42,
        external_pr_id="pr-42",
        title="Test PR",
        author="testuser",
        state="opened",
        head_branch="feature",
        base_branch="main",
        head_sha="abc123",
        pr_url="https://github.com/test/repo/pull/42",
    )
    db_session.commit()

    # Try to get PR
    response = authenticated_client.get(f"/pull-requests/{pr.id}")

    # Verify error
    assert response.status_code == 403
    assert "Access denied" in response.json()["detail"]


def test_get_pull_request_invalid_id(
    authenticated_client: TestClient,
):
    """Test that invalid PR ID returns 400."""
    response = authenticated_client.get("/pull-requests/not-a-uuid")

    assert response.status_code == 400
    assert "Invalid pull request ID format" in response.json()["detail"]


def test_get_pull_request_not_found(
    authenticated_client: TestClient,
):
    """Test that non-existent PR returns 404."""
    fake_id = uuid4()
    response = authenticated_client.get(f"/pull-requests/{fake_id}")

    assert response.status_code == 404
    assert "Pull request not found" in response.json()["detail"]


def test_trigger_pull_request_review_queues_job(
    authenticated_client: TestClient,
    test_app,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
    db_session: Session,
):
    """Test that triggering review publishes message to queue."""
    from api.plugins.faststream import get_faststream_broker

    _user, org, _membership = user_with_organization

    # Get the identity username so PR author matches (required for author check)
    identities = db_get_user_identities(db_session, _user.id)
    author_username = identities[0].username

    # Create repository and PR
    repository = db_create_repository(
        db=db_session,
        organization_id=org.id,
        external_repo_id="12345",
        name="test-repo",
        web_url="https://github.com/test/repo",
        provider="github",
        provider_url="https://github.com",
    )

    pr = db_create_pull_request(
        db=db_session,
        organization_id=org.id,
        repository_id=repository.id,
        pr_number=42,
        external_pr_id="pr-42",
        title="Test PR",
        author=author_username,
        state="opened",
        head_branch="feature",
        base_branch="main",
        head_sha="abc123",
        pr_url="https://github.com/test/repo/pull/42",
    )
    db_session.commit()

    # Create a mock broker that tracks publish calls
    mock_broker = MagicMock()
    mock_broker.publish = AsyncMock(return_value=None)

    # Override the FastStream broker dependency with our tracked mock
    web_plugin = test_app.web
    web_plugin.app.dependency_overrides[get_faststream_broker] = lambda: mock_broker

    try:
        # Trigger review
        response = authenticated_client.post(
            f"/pull-requests/{pr.id}/review",
            json={"commit_sha": "abc1234567"},
        )

        # Should return 202 Accepted
        assert response.status_code == 202, f"Got {response.status_code}: {response.json()}"
        data = response.json()
        assert data["status"] == "queued"
        assert data["commit_sha"] == "abc1234567"
        assert data["pull_request_id"] == str(pr.id)
        assert "execution_id" in data

        # Verify broker.publish was called 2 times (job + PR event)
        assert mock_broker.publish.called
        assert mock_broker.publish.call_count == 2

        # First call: job message (stream-based)
        first_call = mock_broker.publish.call_args_list[0]
        job_message = first_call[0][0]  # First positional arg

        assert first_call[1]["stream"] == "reviewate.review.jobs"
        assert first_call[1]["maxlen"] == 10000
        assert job_message["commit_sha"] == "abc1234567"
        assert job_message["pull_request_number"] == 42
        assert job_message["platform"] == org.provider

        # Second call: PR event (Pub/Sub — stays channel=)
        second_call = mock_broker.publish.call_args_list[1]
        pr_event = second_call[0][0]

        assert second_call[1]["channel"] == "reviewate.events.pull_requests"
        assert pr_event["action"] == "execution_created"
        assert pr_event["latest_execution_status"] == "queued"
        assert "latest_execution_id" in pr_event
    finally:
        # Note: dependency_overrides will be cleared by the fixture cleanup
        pass


def test_trigger_pull_request_review_requires_authentication(
    client: TestClient,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
    db_session: Session,
):
    """Test that trigger review requires authentication."""
    _user, org, _membership = user_with_organization

    # Create repository and PR
    repository = db_create_repository(
        db=db_session,
        organization_id=org.id,
        external_repo_id="12345",
        name="test-repo",
        web_url="https://github.com/test/repo",
        provider="github",
        provider_url="https://github.com",
    )

    pr = db_create_pull_request(
        db=db_session,
        organization_id=org.id,
        repository_id=repository.id,
        pr_number=42,
        external_pr_id="pr-42",
        title="Test PR",
        author="testuser",
        state="opened",
        head_branch="feature",
        base_branch="main",
        head_sha="abc123",
        pr_url="https://github.com/test/repo/pull/42",
    )
    db_session.commit()

    # Try without auth
    response = client.post(
        f"/pull-requests/{pr.id}/review",
        json={"commit_sha": "abc1234"},
    )

    # Verify error
    assert response.status_code == 401


def test_trigger_pull_request_review_requires_membership(
    authenticated_client: TestClient,
    create_user: User,
    create_organization: Organization,
    db_session: Session,
):
    """Test that trigger review requires organization membership."""
    # Create repository and PR in organization where user is not a member
    repository = db_create_repository(
        db=db_session,
        organization_id=create_organization.id,
        external_repo_id="12345",
        name="test-repo",
        web_url="https://github.com/test/repo",
        provider="github",
        provider_url="https://github.com",
    )

    pr = db_create_pull_request(
        db=db_session,
        organization_id=create_organization.id,
        repository_id=repository.id,
        pr_number=42,
        external_pr_id="pr-42",
        title="Test PR",
        author="testuser",
        state="opened",
        head_branch="feature",
        base_branch="main",
        head_sha="abc123",
        pr_url="https://github.com/test/repo/pull/42",
    )
    db_session.commit()

    # Try to trigger review
    response = authenticated_client.post(
        f"/pull-requests/{pr.id}/review",
        json={"commit_sha": "abc1234"},
    )

    # Verify error
    assert response.status_code == 403
    assert "Access denied" in response.json()["detail"]


def test_trigger_pull_request_review_non_author_forbidden(
    authenticated_client: TestClient,
    test_app,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
    db_session: Session,
):
    """Test that non-author cannot trigger a review (403)."""
    _user, org, _membership = user_with_organization

    # Create repository and PR with a DIFFERENT author than the authenticated user
    repository = db_create_repository(
        db=db_session,
        organization_id=org.id,
        external_repo_id="12345",
        name="test-repo",
        web_url="https://github.com/test/repo",
        provider="github",
        provider_url="https://github.com",
    )

    pr = db_create_pull_request(
        db=db_session,
        organization_id=org.id,
        repository_id=repository.id,
        pr_number=42,
        external_pr_id="pr-42",
        title="Test PR",
        author="someone-else",
        state="opened",
        head_branch="feature",
        base_branch="main",
        head_sha="abc123",
        pr_url="https://github.com/test/repo/pull/42",
    )
    db_session.commit()

    # Try to trigger review as non-author
    response = authenticated_client.post(
        f"/pull-requests/{pr.id}/review",
        json={"commit_sha": "abc1234"},
    )

    # Verify 403
    assert response.status_code == 403
    assert "Only the PR author can trigger a manual review" in response.json()["detail"]


# ============================================================================
# Dashboard Stats Tests
# ============================================================================


def test_dashboard_stats_empty(
    authenticated_client: TestClient,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
    db_session: Session,
):
    """Test dashboard stats with no executions returns zeroes/null."""
    response = authenticated_client.get("/pull-requests/stats")

    assert response.status_code == 200
    data = response.json()
    assert data["active_repos"] == 0
    assert data["avg_review_time_seconds"] is None
    assert data["prs_reviewed"] == 0
    assert data["active_repos_change"]["trend"] == "neutral"
    assert data["avg_review_time_change"]["trend"] == "neutral"
    assert data["prs_reviewed_change"]["trend"] == "neutral"


def test_dashboard_stats_with_executions(
    authenticated_client: TestClient,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
    db_session: Session,
):
    """Test dashboard stats with completed executions returns correct counts."""
    _user, org, _membership = user_with_organization

    # Create two repositories
    repo1 = db_create_repository(
        db=db_session,
        organization_id=org.id,
        external_repo_id="repo-1",
        name="repo-1",
        web_url="https://github.com/test/repo-1",
        provider="github",
        provider_url="https://github.com",
    )
    repo2 = db_create_repository(
        db=db_session,
        organization_id=org.id,
        external_repo_id="repo-2",
        name="repo-2",
        web_url="https://github.com/test/repo-2",
        provider="github",
        provider_url="https://github.com",
    )

    # Create PRs
    pr1 = db_create_pull_request(
        db=db_session,
        organization_id=org.id,
        repository_id=repo1.id,
        pr_number=1,
        external_pr_id="pr-1",
        title="PR 1",
        author="user1",
        state="opened",
        head_branch="feature-1",
        base_branch="main",
        head_sha="sha1",
        pr_url="https://github.com/test/repo-1/pull/1",
    )
    pr2 = db_create_pull_request(
        db=db_session,
        organization_id=org.id,
        repository_id=repo2.id,
        pr_number=2,
        external_pr_id="pr-2",
        title="PR 2",
        author="user2",
        state="opened",
        head_branch="feature-2",
        base_branch="main",
        head_sha="sha2",
        pr_url="https://github.com/test/repo-2/pull/2",
    )

    # Create completed executions (within current 7 days)
    exec1 = db_create_execution(
        db=db_session,
        organization_id=org.id,
        repository_id=repo1.id,
        pull_request_id=pr1.id,
        pr_number=1,
        commit_sha="sha1",
        status="completed",
    )
    exec2 = db_create_execution(
        db=db_session,
        organization_id=org.id,
        repository_id=repo2.id,
        pull_request_id=pr2.id,
        pr_number=2,
        commit_sha="sha2",
        status="completed",
    )

    # Set updated_at to simulate review duration (5 minutes each)
    exec1.updated_at = exec1.created_at + timedelta(minutes=5)
    exec2.updated_at = exec2.created_at + timedelta(minutes=5)
    db_session.commit()

    response = authenticated_client.get("/pull-requests/stats")

    assert response.status_code == 200
    data = response.json()

    # 2 distinct repos with completed reviews
    assert data["active_repos"] == 2
    # 2 distinct PRs reviewed
    assert data["prs_reviewed"] == 2
    # Avg review time should be ~300 seconds (5 minutes)
    assert data["avg_review_time_seconds"] is not None
    assert data["avg_review_time_seconds"] > 0


def test_dashboard_stats_requires_authentication(
    client: TestClient,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
):
    """Test that dashboard stats requires authentication."""
    response = client.get("/pull-requests/stats")
    assert response.status_code == 401


# ============================================================================
# Multi-Author Filter Tests (GitHub + GitLab usernames)
# ============================================================================


def test_list_all_pull_requests_multi_author_filter(
    authenticated_client: TestClient,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
    db_session: Session,
):
    """Test that author filter accepts multiple usernames.

    When a user has both GitHub and GitLab connected, their usernames may differ.
    The 'My PRs' filter sends both usernames so PRs from either provider are matched.
    """
    _user, org, _membership = user_with_organization

    # Create repository
    repository = db_create_repository(
        db=db_session,
        organization_id=org.id,
        external_repo_id="multi-author-repo",
        name="test-repo",
        web_url="https://github.com/test/repo",
        provider="github",
        provider_url="https://github.com",
    )

    # Create PRs with different author usernames (simulating GitHub vs GitLab usernames)
    _ = db_create_pull_request(
        db=db_session,
        organization_id=org.id,
        repository_id=repository.id,
        pr_number=1,
        external_pr_id="pr-gh-1",
        title="GitHub PR",
        author="adamsaimi",  # GitHub username
        state="open",
        head_branch="feature-1",
        base_branch="main",
        head_sha="sha1",
        pr_url="https://github.com/test/repo/pull/1",
    )

    _ = db_create_pull_request(
        db=db_session,
        organization_id=org.id,
        repository_id=repository.id,
        pr_number=2,
        external_pr_id="pr-gl-2",
        title="GitLab MR",
        author="adsa",  # GitLab username (different!)
        state="open",
        head_branch="feature-2",
        base_branch="main",
        head_sha="sha2",
        pr_url="https://gitlab.com/test/repo/-/merge_requests/2",
    )

    _pr_other = db_create_pull_request(
        db=db_session,
        organization_id=org.id,
        repository_id=repository.id,
        pr_number=3,
        external_pr_id="pr-other-3",
        title="Someone Else's PR",
        author="other-user",
        state="open",
        head_branch="feature-3",
        base_branch="main",
        head_sha="sha3",
        pr_url="https://github.com/test/repo/pull/3",
    )
    db_session.commit()

    # Filter with both usernames (simulates "My PRs" with multi-provider identity)
    response = authenticated_client.get(
        "/pull-requests",
        params={"author": ["adamsaimi", "adsa"]},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["pagination"]["total"] == 2

    returned_authors = {pr["author"] for pr in data["objects"]}
    assert returned_authors == {"adamsaimi", "adsa"}


def test_list_all_pull_requests_single_author_filter(
    authenticated_client: TestClient,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
    db_session: Session,
):
    """Test that author filter still works with a single username."""
    _user, org, _membership = user_with_organization

    repository = db_create_repository(
        db=db_session,
        organization_id=org.id,
        external_repo_id="single-author-repo",
        name="test-repo",
        web_url="https://github.com/test/repo",
        provider="github",
        provider_url="https://github.com",
    )

    db_create_pull_request(
        db=db_session,
        organization_id=org.id,
        repository_id=repository.id,
        pr_number=1,
        external_pr_id="pr-single-1",
        title="My PR",
        author="testuser",
        state="open",
        head_branch="feature-1",
        base_branch="main",
        head_sha="sha1",
        pr_url="https://github.com/test/repo/pull/1",
    )

    db_create_pull_request(
        db=db_session,
        organization_id=org.id,
        repository_id=repository.id,
        pr_number=2,
        external_pr_id="pr-single-2",
        title="Other PR",
        author="other",
        state="open",
        head_branch="feature-2",
        base_branch="main",
        head_sha="sha2",
        pr_url="https://github.com/test/repo/pull/2",
    )
    db_session.commit()

    # Single author filter (backwards compatible)
    response = authenticated_client.get(
        "/pull-requests",
        params={"author": ["testuser"]},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["pagination"]["total"] == 1
    assert data["objects"][0]["author"] == "testuser"


def test_list_all_pull_requests_no_author_filter(
    authenticated_client: TestClient,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
    db_session: Session,
):
    """Test that omitting author filter returns all PRs."""
    _user, org, _membership = user_with_organization

    repository = db_create_repository(
        db=db_session,
        organization_id=org.id,
        external_repo_id="no-filter-repo",
        name="test-repo",
        web_url="https://github.com/test/repo",
        provider="github",
        provider_url="https://github.com",
    )

    db_create_pull_request(
        db=db_session,
        organization_id=org.id,
        repository_id=repository.id,
        pr_number=1,
        external_pr_id="pr-nofilter-1",
        title="PR 1",
        author="user1",
        state="open",
        head_branch="f1",
        base_branch="main",
        head_sha="s1",
        pr_url="https://github.com/test/repo/pull/1",
    )

    db_create_pull_request(
        db=db_session,
        organization_id=org.id,
        repository_id=repository.id,
        pr_number=2,
        external_pr_id="pr-nofilter-2",
        title="PR 2",
        author="user2",
        state="open",
        head_branch="f2",
        base_branch="main",
        head_sha="s2",
        pr_url="https://github.com/test/repo/pull/2",
    )
    db_session.commit()

    # No author filter — should return all PRs
    response = authenticated_client.get("/pull-requests")

    assert response.status_code == 200
    data = response.json()
    assert data["pagination"]["total"] == 2
