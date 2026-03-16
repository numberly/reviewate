"""FastAPI dependencies specific to pull request endpoints."""

from uuid import UUID

from fastapi import Depends, HTTPException, Path

from api.context import get_current_app
from api.database import (
    db_get_organization_memberships_by_identity,
    db_get_pull_request_by_id,
    db_get_user_organization_ids,
)
from api.models import PullRequest, User
from api.routers.auth import get_current_user
from api.utils import parse_uuid


async def get_user_org_ids(
    current_user: User = Depends(get_current_user),
) -> list[UUID]:
    """Return organization IDs the current user has access to."""
    identity_ids = [identity.id for identity in current_user.identities]
    app = get_current_app()
    with app.database.session() as db:
        return db_get_user_organization_ids(db, identity_ids)


async def verify_pull_request_access(
    pr_id: str = Path(description="Pull request ID (UUID)"),
    current_user: User = Depends(get_current_user),
) -> PullRequest:
    """Verify user has access to a pull request via organization membership.

    Returns:
        PullRequest if user has access

    Raises:
        HTTPException: 400 if invalid UUID, 404 if not found, 403 if no access
    """
    pr_uuid = parse_uuid(pr_id, "pull request ID")

    identity_ids = [identity.id for identity in current_user.identities]

    app = get_current_app()
    with app.database.session() as db:
        pr = db_get_pull_request_by_id(db, pr_uuid)
        if not pr:
            raise HTTPException(status_code=404, detail="Pull request not found")

        membership = db_get_organization_memberships_by_identity(
            db, identity_ids, pr.organization_id
        )

    if not membership:
        raise HTTPException(status_code=403, detail="Access denied")

    return pr
