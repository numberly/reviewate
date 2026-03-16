"""Tests for GitLab webhook endpoints.

Tests for GitLab MR webhook handlers at /webhooks/gitlab.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.database import db_create_pull_request, db_create_repository
from api.models import Organization, OrganizationMembership, PullRequest, User

# =============================================================================
# GitLab MR Webhook Tests (POST /webhooks/gitlab)
# =============================================================================


def test_gitlab_mr_webhook_creates_pull_request(
    client: TestClient,
    test_app,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
    db_session: Session,
):
    """Test that GitLab MR open event creates a pull request record."""
    _, org, _ = user_with_organization

    # Create a repository for this organization
    repository = db_create_repository(
        db=db_session,
        organization_id=org.id,
        external_repo_id="12345",
        name="test-repo",
        web_url="https://gitlab.com/test/repo",
        provider="gitlab",
        provider_url="https://gitlab.com",
    )
    db_session.commit()

    # Prepare GitLab MR webhook payload
    webhook_payload = {
        "object_kind": "merge_request",
        "user": {"username": "testuser", "id": 1},
        "object_attributes": {
            "id": 99999,
            "iid": 42,
            "title": "Add new feature",
            "action": "open",
            "state": "opened",
            "source_branch": "feature-branch",
            "target_branch": "main",
            "url": "https://gitlab.com/test/repo/-/merge_requests/42",
            "author": {"username": "testuser"},
        },
        "project": {
            "id": 12345,
            "name": "test-repo",
        },
    }

    # Send webhook
    response = client.post(
        "/webhooks/gitlab",
        json=webhook_payload,
        headers={"x-gitlab-token": "test-webhook-secret"},
    )

    # Verify response
    assert response.status_code == 202
    data = response.json()
    assert data["processed"] is True
    assert "created successfully" in data["message"]

    # Verify pull request was created
    pr = (
        db_session.query(PullRequest)
        .filter(PullRequest.repository_id == repository.id, PullRequest.pr_number == 42)
        .first()
    )
    assert pr is not None
    assert pr.title == "Add new feature"
    assert pr.author == "testuser"
    assert pr.state == "opened"
    assert pr.head_branch == "feature-branch"
    assert pr.base_branch == "main"
    assert pr.external_pr_id == "99999"


def test_gitlab_mr_webhook_updates_existing_pull_request(
    client: TestClient,
    test_app,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
    db_session: Session,
):
    """Test that GitLab MR update event updates existing pull request."""
    _, org, _ = user_with_organization

    # Create repository and initial PR
    repository = db_create_repository(
        db=db_session,
        organization_id=org.id,
        external_repo_id="12345",
        name="test-repo",
        web_url="https://gitlab.com/test/repo",
        provider="gitlab",
        provider_url="https://gitlab.com",
    )

    initial_pr = db_create_pull_request(
        db=db_session,
        organization_id=org.id,
        repository_id=repository.id,
        pr_number=42,
        external_pr_id="99999",
        title="Old title",
        author="oldauthor",
        state="opened",
        head_branch="feature",
        base_branch="main",
        head_sha="abc123",
        pr_url="https://gitlab.com/test/repo/-/merge_requests/42",
    )
    db_session.commit()

    # Prepare update webhook payload
    webhook_payload = {
        "object_kind": "merge_request",
        "user": {"username": "testuser", "id": 1},
        "object_attributes": {
            "id": 99999,
            "iid": 42,
            "title": "Updated title",
            "action": "update",
            "state": "opened",
            "source_branch": "feature-updated",
            "target_branch": "develop",
            "url": "https://gitlab.com/test/repo/-/merge_requests/42",
            "author": {"username": "newauthor"},
        },
        "project": {
            "id": 12345,
            "name": "test-repo",
        },
    }

    # Send webhook
    response = client.post(
        "/webhooks/gitlab",
        json=webhook_payload,
        headers={"x-gitlab-token": "test-webhook-secret"},
    )

    # Verify response
    assert response.status_code == 202
    data = response.json()
    assert data["processed"] is True
    assert "updated successfully" in data["message"]

    # Verify pull request was updated
    db_session.refresh(initial_pr)
    assert initial_pr.title == "Updated title"
    assert initial_pr.author == initial_pr.author
    assert initial_pr.head_branch == "feature-updated"
    assert initial_pr.base_branch == "develop"


def test_gitlab_mr_webhook_rejects_invalid_token(
    client: TestClient,
    test_app,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
    db_session: Session,
):
    """Test that GitLab MR webhook rejects requests with invalid token."""
    _, org, _ = user_with_organization

    _repository = db_create_repository(
        db=db_session,
        organization_id=org.id,
        external_repo_id="12345",
        name="test-repo",
        web_url="https://gitlab.com/test/repo",
        provider="gitlab",
        provider_url="https://gitlab.com",
    )
    db_session.commit()

    webhook_payload = {
        "object_kind": "merge_request",
        "user": {"username": "testuser", "id": 1},
        "object_attributes": {
            "id": 99999,
            "iid": 42,
            "title": "Test MR",
            "action": "open",
            "state": "opened",
            "source_branch": "feature",
            "target_branch": "main",
            "url": "https://gitlab.com/test/repo/-/merge_requests/42",
            "author": {"username": "testuser"},
        },
        "project": {
            "id": 12345,
            "name": "test-repo",
        },
    }

    # Send webhook with wrong token
    response = client.post(
        "/webhooks/gitlab",
        json=webhook_payload,
        headers={"x-gitlab-token": "wrong-token"},
    )

    # Verify error response
    assert response.status_code == 401
    assert "Invalid webhook token" in response.json()["detail"]


def test_gitlab_mr_webhook_requires_token_header(
    client: TestClient,
    test_app,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
    db_session: Session,
):
    """Test that GitLab MR webhook requires X-Gitlab-Token header."""
    _, org, _ = user_with_organization

    _repository = db_create_repository(
        db=db_session,
        organization_id=org.id,
        external_repo_id="12345",
        name="test-repo",
        web_url="https://gitlab.com/test/repo",
        provider="gitlab",
        provider_url="https://gitlab.com",
    )
    db_session.commit()

    webhook_payload = {
        "object_kind": "merge_request",
        "user": {"username": "testuser", "id": 1},
        "object_attributes": {
            "id": 99999,
            "iid": 42,
            "title": "Test MR",
            "action": "open",
            "state": "opened",
            "source_branch": "feature",
            "target_branch": "main",
            "url": "https://gitlab.com/test/repo/-/merge_requests/42",
            "author": {"username": "testuser"},
        },
        "project": {
            "id": 12345,
            "name": "test-repo",
        },
    }

    # Send webhook without token header
    response = client.post("/webhooks/gitlab", json=webhook_payload)

    # Verify error response
    assert response.status_code == 401
    assert "Missing X-Gitlab-Token header" in response.json()["detail"]


def test_gitlab_mr_webhook_ignores_non_mr_events(
    client: TestClient,
    test_app,
    db_session: Session,
):
    """Test that GitLab webhook ignores non-merge-request events."""
    webhook_payload = {
        "object_kind": "push",  # Not a merge request
        "user": {"username": "testuser", "id": 1},
        "project": {"id": 123, "name": "test"},
        "object_attributes": {},  # Required by schema
    }

    # Send webhook
    response = client.post(
        "/webhooks/gitlab",
        json=webhook_payload,
        headers={"x-gitlab-token": "test-webhook-secret"},
    )

    # Verify response - ignored but not error
    assert response.status_code == 202
    data = response.json()
    assert data["processed"] is False
    assert "not supported" in data["message"]


def test_gitlab_mr_webhook_processes_close_action(
    client: TestClient,
    test_app,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
    db_session: Session,
):
    """Test that GitLab MR webhook processes close actions (upserts PR with closed state)."""
    _, org, _ = user_with_organization

    _repository = db_create_repository(
        db=db_session,
        organization_id=org.id,
        external_repo_id="12345",
        name="test-repo",
        web_url="https://gitlab.com/test/repo",
        provider="gitlab",
        provider_url="https://gitlab.com",
    )
    db_session.commit()

    webhook_payload = {
        "object_kind": "merge_request",
        "user": {"username": "testuser", "id": 1},
        "object_attributes": {
            "id": 99999,
            "iid": 42,
            "title": "Closed MR",
            "action": "close",
            "state": "closed",
            "source_branch": "feature",
            "target_branch": "main",
            "url": "https://gitlab.com/test/repo/-/merge_requests/42",
            "author": {"username": "testuser"},
        },
        "project": {
            "id": 12345,
            "name": "test-repo",
        },
    }

    # Send webhook
    response = client.post(
        "/webhooks/gitlab",
        json=webhook_payload,
        headers={"x-gitlab-token": "test-webhook-secret"},
    )

    # Verify response - processed (PR upserted with closed state)
    assert response.status_code == 202
    data = response.json()
    assert data["processed"] is True
    assert "created successfully" in data["message"]

    # Verify PR was created with closed state
    pr = (
        db_session.query(PullRequest)
        .filter(PullRequest.repository_id == _repository.id, PullRequest.pr_number == 42)
        .first()
    )
    assert pr is not None
    assert pr.state == "closed"


def test_gitlab_mr_webhook_repository_not_found(
    client: TestClient,
    test_app,
    db_session: Session,
):
    """Test that GitLab MR webhook returns 404 if repository not found."""
    webhook_payload = {
        "object_kind": "merge_request",
        "user": {"username": "testuser", "id": 1},
        "object_attributes": {
            "id": 99999,
            "iid": 42,
            "title": "Test MR",
            "action": "open",
            "state": "opened",
            "source_branch": "feature",
            "target_branch": "main",
            "url": "https://gitlab.com/test/repo/-/merge_requests/42",
            "author": {"username": "testuser"},
        },
        "project": {
            "id": 99999,  # Non-existent project
            "name": "non-existent-repo",
        },
    }

    # Send webhook
    response = client.post(
        "/webhooks/gitlab",
        json=webhook_payload,
        headers={"x-gitlab-token": "test-webhook-secret"},
    )

    # Verify error response
    assert response.status_code == 404
    assert "Repository not found" in response.json()["detail"]
