"""Tests for repositories endpoints."""

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.database import db_create_repository
from api.models import Organization, OrganizationMembership, Repository, User


def test_list_organization_repositories(
    authenticated_client: TestClient,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
    db_session: Session,
):
    """Test listing repositories for an organization."""
    _user, org, _membership = user_with_organization

    # Create some repositories for this organization
    _repo1 = db_create_repository(
        db=db_session,
        organization_id=org.id,
        external_repo_id="123",
        name="repo-one",
        web_url="https://github.com/org/repo-one",
        provider="github",
        provider_url="https://github.com",
    )

    _repo2 = db_create_repository(
        db=db_session,
        organization_id=org.id,
        external_repo_id="456",
        name="repo-two",
        web_url="https://github.com/org/repo-two",
        provider="github",
        provider_url="https://github.com",
    )
    db_session.commit()

    # List repositories
    response = authenticated_client.get(f"/organizations/{org.id}/repositories")

    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert "objects" in data
    assert len(data["objects"]) == 2

    # Verify repository data
    repo_names = {repo["name"] for repo in data["objects"]}
    assert "repo-one" in repo_names
    assert "repo-two" in repo_names


def test_list_organization_repositories_empty(
    authenticated_client: TestClient,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
    db_session: Session,
):
    """Test listing repositories when organization has none."""
    _user, org, _membership = user_with_organization

    # List repositories (should be empty)
    response = authenticated_client.get(f"/organizations/{org.id}/repositories")

    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert "objects" in data
    assert len(data["objects"]) == 0


def test_list_organization_repositories_requires_authentication(
    client: TestClient,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
    db_session: Session,
):
    """Test that listing repositories requires authentication."""
    _user, org, _membership = user_with_organization

    # Try to list repositories without authentication
    response = client.get(f"/organizations/{org.id}/repositories")

    # Verify error response
    assert response.status_code == 401


def test_list_organization_repositories_requires_membership(
    authenticated_client: TestClient,
    create_organization: Organization,
    db_session: Session,
):
    """Test that listing repositories requires organization membership."""
    # Create an organization the user is NOT a member of
    other_org = create_organization

    # Try to list repositories
    response = authenticated_client.get(f"/organizations/{other_org.id}/repositories")

    # Verify error response
    assert response.status_code == 403


def test_delete_repository(
    authenticated_client: TestClient,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
    db_session: Session,
):
    """Test deleting a repository."""
    _user, org, _membership = user_with_organization

    # Create a repository
    repository = db_create_repository(
        db=db_session,
        organization_id=org.id,
        external_repo_id="123",
        name="to-delete",
        web_url="https://github.com/org/to-delete",
        provider="github",
        provider_url="https://github.com",
    )
    db_session.commit()

    repo_id = str(repository.id)

    # Delete the repository
    response = authenticated_client.delete(f"/repositories/{repo_id}")

    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Repository deleted successfully"
    assert data["repository_id"] == repo_id

    # Verify repository was deleted
    repo = db_session.query(Repository).filter(Repository.id == repository.id).first()
    assert repo is None


def test_delete_repository_requires_authentication(
    client: TestClient,
    user_with_organization: tuple[User, Organization, OrganizationMembership],
    db_session: Session,
):
    """Test that deleting a repository requires authentication."""
    _user, org, _membership = user_with_organization

    repository = db_create_repository(
        db=db_session,
        organization_id=org.id,
        external_repo_id="123",
        name="test-repo",
        web_url="https://github.com/org/test-repo",
        provider="github",
        provider_url="https://github.com",
    )
    db_session.commit()

    # Try to delete without authentication
    response = client.delete(f"/repositories/{repository.id}")

    # Verify error response
    assert response.status_code == 401


def test_delete_repository_requires_organization_membership(
    authenticated_client: TestClient,
    create_organization: Organization,
    db_session: Session,
):
    """Test that deleting a repository requires organization membership."""
    # Create a repository in an organization the user is NOT a member of
    other_org = create_organization

    repository = db_create_repository(
        db=db_session,
        organization_id=other_org.id,
        external_repo_id="123",
        name="other-repo",
        web_url="https://github.com/other/repo",
        provider="github",
        provider_url="https://github.com",
    )
    db_session.commit()

    # Try to delete the repository
    response = authenticated_client.delete(f"/repositories/{repository.id}")

    # Verify error response
    assert response.status_code == 403
    assert "don't have access" in response.json()["detail"]


def test_delete_repository_not_found(
    authenticated_client: TestClient,
    db_session: Session,
):
    """Test deleting a non-existent repository."""
    fake_id = uuid4()

    # Try to delete non-existent repository
    response = authenticated_client.delete(f"/repositories/{fake_id}")

    # Verify error response
    assert response.status_code == 404
    assert "Repository not found" in response.json()["detail"]


def test_delete_repository_invalid_id(
    authenticated_client: TestClient,
    db_session: Session,
):
    """Test deleting a repository with invalid ID format."""
    # Try to delete with invalid UUID
    response = authenticated_client.delete("/repositories/not-a-uuid")

    # Verify error response
    assert response.status_code == 400
    assert (
        "Invalid" in response.json()["detail"]
    )  # Could be "Invalid UUID" or "Invalid repository ID format"
