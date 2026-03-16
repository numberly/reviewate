"""Database operations for Repository and RepositoryMembership models."""

from uuid import UUID

from sqlalchemy.orm import Session

from api.models.repositories import Repository, RepositoryMembership


def db_create_repository(
    db: Session,
    organization_id: UUID,
    external_repo_id: str,
    name: str,
    web_url: str,
    provider: str,
    provider_url: str,
    gitlab_access_token_encrypted: str | None = None,
    avatar_url: str | None = None,
) -> Repository:
    """Create a new repository.

    Args:
        db: Database session
        organization_id: Organization ID
        external_repo_id: External repo ID from platform
        name: Repository name
        web_url: Repository web URL
        provider: Provider type (github or gitlab)
        provider_url: Provider URL (e.g., https://github.com or custom GitLab instance)
        gitlab_access_token_encrypted: Encrypted GitLab access token (optional)
        avatar_url: Repository avatar URL (owner's avatar) (optional)

    Returns:
        Created Repository
    """
    repository = Repository(
        organization_id=organization_id,
        external_repo_id=external_repo_id,
        name=name,
        web_url=web_url,
        provider=provider,
        provider_url=provider_url,
        gitlab_access_token_encrypted=gitlab_access_token_encrypted,
        avatar_url=avatar_url,
    )
    db.add(repository)
    db.commit()
    db.refresh(repository)

    return repository


def db_create_repository_membership(
    db: Session,
    user_id: UUID,
    repository_id: UUID,
    role: str = "member",
) -> RepositoryMembership:
    """Create a repository membership.

    Args:
        db: Database session
        user_id: User ID
        repository_id: Repository ID
        role: User role for repository (default: "member")

    Returns:
        Created RepositoryMembership
    """
    membership = RepositoryMembership(
        user_id=user_id,
        repository_id=repository_id,
        role=role,
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)

    return membership


def db_sync_repository_membership(
    db: Session,
    user_id: UUID,
    repository_id: UUID,
    role: str = "member",
) -> RepositoryMembership:
    """Create repository membership if it doesn't exist, or return existing one.

    This is used during OAuth login to auto-add users to repositories
    in organizations they belong to.

    Args:
        db: Database session
        user_id: User ID
        repository_id: Repository ID
        role: User role for repository (default: "member")

    Returns:
        RepositoryMembership (either existing or newly created)
    """
    # Check if membership already exists
    existing = (
        db.query(RepositoryMembership)
        .filter(
            RepositoryMembership.user_id == user_id,
            RepositoryMembership.repository_id == repository_id,
        )
        .first()
    )
    if existing:
        return existing

    # Create new membership
    return db_create_repository_membership(db, user_id, repository_id, role)


def db_get_repository_by_external_id(
    db: Session,
    external_repo_id: str,
) -> Repository | None:
    """Get repository by external repo ID.

    Args:
        db: Database session
        external_repo_id: External repo ID from platform

    Returns:
        Repository if found, None otherwise
    """
    return db.query(Repository).filter(Repository.external_repo_id == external_repo_id).first()


def db_get_repositories_by_organization(
    db: Session,
    organization_id: UUID,
) -> list[Repository]:
    """Get all repositories for an organization.

    Args:
        db: Database session
        organization_id: Organization ID

    Returns:
        List of repositories for the organization
    """
    return db.query(Repository).filter(Repository.organization_id == organization_id).all()


def db_get_repository_by_id(
    db: Session,
    repository_id: UUID,
) -> Repository | None:
    """Get repository by ID.

    Args:
        db: Database session
        repository_id: Repository ID

    Returns:
        Repository if found, None otherwise
    """
    return db.query(Repository).filter(Repository.id == repository_id).first()


def db_delete_repository(
    db: Session,
    external_repo_id: str,
) -> bool:
    """Delete repository by external repo ID.

    Args:
        db: Database session
        external_repo_id: External repo ID from platform

    Returns:
        True if repository was deleted, False if not found
    """
    repository = db_get_repository_by_external_id(db, external_repo_id)
    if repository:
        db.delete(repository)  # Cascade deletes memberships
        db.commit()
        return True
    return False


def db_delete_repository_by_id(
    db: Session,
    repository_id: UUID,
) -> bool:
    """Delete repository by ID.

    Args:
        db: Database session
        repository_id: Repository ID

    Returns:
        True if repository was deleted, False if not found
    """
    repository = db_get_repository_by_id(db, repository_id)
    if repository:
        db.delete(repository)  # Cascade deletes memberships
        db.flush()
        return True
    return False


def db_update_repository_settings(
    db: Session,
    repository_id: UUID,
    **kwargs: str | bool | None,
) -> Repository | None:
    """Update repository settings.

    Only updates fields that are explicitly passed. Pass None to clear
    an override and inherit from organization. Supports:
    - automatic_review_trigger: str | None
    - automatic_summary_trigger: str | None

    Args:
        db: Database session
        repository_id: Repository ID
        **kwargs: Fields to update

    Returns:
        Updated Repository or None if not found
    """
    repository = db_get_repository_by_id(db, repository_id)
    if not repository:
        return None

    for key, value in kwargs.items():
        if hasattr(repository, key):
            setattr(repository, key, value)

    db.commit()
    db.refresh(repository)
    return repository


def db_reset_repository_settings(
    db: Session,
    repository_id: UUID,
) -> Repository | None:
    """Reset repository settings to inherit from organization.

    Sets all settings fields to None so they inherit from the organization.

    Args:
        db: Database session
        repository_id: Repository ID

    Returns:
        Updated Repository or None if not found
    """
    repository = db_get_repository_by_id(db, repository_id)
    if not repository:
        return None

    repository.automatic_review_trigger = None
    repository.automatic_summary_trigger = None

    db.commit()
    db.refresh(repository)
    return repository
