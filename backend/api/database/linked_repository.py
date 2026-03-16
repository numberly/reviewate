"""Database operations for LinkedRepository model."""

from uuid import UUID

from sqlalchemy.orm import Session

from api.models.linked_repositories import LinkedRepository
from api.models.repositories import Repository


def db_get_org_linked_repos(
    db: Session,
    organization_id: UUID,
) -> list[LinkedRepository]:
    """Get all linked repositories for an organization.

    Args:
        db: Database session
        organization_id: Organization ID

    Returns:
        List of LinkedRepository records for the organization
    """
    return (
        db.query(LinkedRepository).filter(LinkedRepository.organization_id == organization_id).all()
    )


def db_get_repo_linked_repos(
    db: Session,
    repository_id: UUID,
) -> list[LinkedRepository]:
    """Get all linked repositories for a specific repository.

    Args:
        db: Database session
        repository_id: Repository ID

    Returns:
        List of LinkedRepository records for the repository
    """
    return db.query(LinkedRepository).filter(LinkedRepository.repository_id == repository_id).all()


def db_get_effective_linked_repos(
    db: Session,
    repository_id: UUID,
) -> list[LinkedRepository]:
    """Get effective linked repositories for a repository (org + repo level, deduplicated).

    Merges organization-level linked repos with repository-specific ones.
    If the same repo is linked at both levels, the repo-level link takes precedence.

    Args:
        db: Database session
        repository_id: Repository ID

    Returns:
        Deduplicated list of LinkedRepository records
    """
    # Get the repository to find its organization
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        return []

    # Get org-level linked repos
    org_linked = db_get_org_linked_repos(db, repository.organization_id)

    # Get repo-level linked repos
    repo_linked = db_get_repo_linked_repos(db, repository_id)

    # Create a map of (provider_url, repo_path) -> LinkedRepository
    # Repo-level takes precedence over org-level
    linked_map: dict[tuple[str, str], LinkedRepository] = {}

    # Add org-level first
    for linked in org_linked:
        key = (linked.linked_provider_url, linked.linked_repo_path)
        linked_map[key] = linked

    # Override with repo-level (takes precedence)
    for linked in repo_linked:
        key = (linked.linked_provider_url, linked.linked_repo_path)
        linked_map[key] = linked

    return list(linked_map.values())


def db_add_linked_repo(
    db: Session,
    linked_provider: str,
    linked_provider_url: str,
    linked_repo_path: str,
    organization_id: UUID | None = None,
    repository_id: UUID | None = None,
    linked_branch: str | None = None,
    display_name: str | None = None,
) -> LinkedRepository:
    """Add a linked repository to an organization or repository.

    Args:
        db: Database session
        linked_provider: Provider type ("github" or "gitlab")
        linked_provider_url: Provider URL (e.g., "https://github.com")
        linked_repo_path: Repository path (e.g., "owner/repo")
        organization_id: Organization ID (mutually exclusive with repository_id)
        repository_id: Repository ID (mutually exclusive with organization_id)
        linked_branch: Optional specific branch to use
        display_name: Optional display name for UI

    Returns:
        Created LinkedRepository

    Raises:
        ValueError: If neither or both organization_id and repository_id are provided
    """
    if (organization_id is None) == (repository_id is None):
        raise ValueError("Exactly one of organization_id or repository_id must be provided")

    linked_repo = LinkedRepository(
        organization_id=organization_id,
        repository_id=repository_id,
        linked_provider=linked_provider,
        linked_provider_url=linked_provider_url,
        linked_repo_path=linked_repo_path,
        linked_branch=linked_branch,
        display_name=display_name,
    )
    db.add(linked_repo)
    db.commit()
    db.refresh(linked_repo)

    return linked_repo


def db_get_linked_repo_by_id(
    db: Session,
    linked_repo_id: UUID,
) -> LinkedRepository | None:
    """Get a linked repository by ID.

    Args:
        db: Database session
        linked_repo_id: LinkedRepository ID

    Returns:
        LinkedRepository if found, None otherwise
    """
    return db.query(LinkedRepository).filter(LinkedRepository.id == linked_repo_id).first()


def db_remove_linked_repo(
    db: Session,
    linked_repo_id: UUID,
) -> bool:
    """Remove a linked repository by ID.

    Args:
        db: Database session
        linked_repo_id: LinkedRepository ID

    Returns:
        True if deleted, False if not found
    """
    linked_repo = db_get_linked_repo_by_id(db, linked_repo_id)
    if linked_repo:
        db.delete(linked_repo)
        db.commit()
        return True
    return False
