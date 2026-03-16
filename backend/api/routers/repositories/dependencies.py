"""FastAPI dependencies for repository access control."""

from fastapi import Depends, HTTPException, Path

from api.context import get_current_app
from api.database import db_get_organization_memberships_by_identity, db_get_repository_by_id
from api.models import OrganizationMembership, Repository, User
from api.routers.auth.dependencies import get_current_user
from api.utils import parse_uuid


async def verify_repository_access(
    repo_id: str = Path(description="Repository ID (UUID)"),
    current_user: User = Depends(get_current_user),
) -> tuple[Repository, OrganizationMembership]:
    """Dependency to verify user has access to a repository's organization.

    Returns:
        Tuple of (Repository, OrganizationMembership)

    Raises:
        HTTPException: 404 if repository not found, 403 if no access
    """
    repository_id = parse_uuid(repo_id, "repository ID")

    identity_ids = [identity.id for identity in current_user.identities]

    app = get_current_app()
    with app.database.session() as db:
        repository = db_get_repository_by_id(db, repository_id)
        if not repository:
            raise HTTPException(status_code=404, detail="Repository not found")

        membership = db_get_organization_memberships_by_identity(
            db, identity_ids, repository.organization_id
        )

    if not membership:
        raise HTTPException(status_code=403, detail="You don't have access to this repository")

    return repository, membership


async def verify_repository_admin(
    repo_id: str = Path(description="Repository ID (UUID)"),
    current_user: User = Depends(get_current_user),
) -> tuple[Repository, OrganizationMembership]:
    """Dependency to verify user has admin access to a repository's organization.

    Returns:
        Tuple of (Repository, OrganizationMembership)

    Raises:
        HTTPException: 404 if repository not found, 403 if no admin access
    """
    repository_id = parse_uuid(repo_id, "repository ID")

    identity_ids = [identity.id for identity in current_user.identities]

    app = get_current_app()
    with app.database.session() as db:
        repository = db_get_repository_by_id(db, repository_id)
        if not repository:
            raise HTTPException(status_code=404, detail="Repository not found")

        membership = db_get_organization_memberships_by_identity(
            db, identity_ids, repository.organization_id
        )

    if not membership:
        raise HTTPException(status_code=403, detail="You don't have access to this repository")

    if membership.role != "admin":
        raise HTTPException(
            status_code=403, detail="Only organization admins can perform this action"
        )

    return repository, membership
