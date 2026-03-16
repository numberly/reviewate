"""FastAPI dependencies for organization access control."""

from fastapi import Depends, HTTPException, Path

from api.context import get_current_app
from api.database import db_get_organization_memberships_by_identity
from api.models import OrganizationMembership, User
from api.routers.auth.dependencies import get_current_user
from api.utils import parse_uuid


async def verify_organization_access(
    org_id: str = Path(description="Organization ID (UUID)"),
    current_user: User = Depends(get_current_user),
) -> OrganizationMembership:
    """Dependency to verify user has access to an organization.

    Looks up all user's provider identities and checks if any have membership.

    Args:
        org_id: Organization UUID string from path parameter
        current_user: Authenticated user from get_current_user dependency

    Returns:
        OrganizationMembership if user has access

    Raises:
        HTTPException: 400 if org_id is not a valid UUID
        HTTPException: 403 if user doesn't have access to organization
    """
    organization_id = parse_uuid(org_id, "organization ID")

    # Use pre-loaded identities from get_current_user (no extra query needed)
    identity_ids = [identity.id for identity in current_user.identities]

    # Find membership for any of the user's identities
    app = get_current_app()
    with app.database.session() as db:
        membership = db_get_organization_memberships_by_identity(db, identity_ids, organization_id)

    if not membership:
        raise HTTPException(
            status_code=403,
            detail="You don't have access to this organization",
        )
    return membership


async def verify_organization_admin(
    org_id: str = Path(description="Organization ID (UUID)"),
    current_user: User = Depends(get_current_user),
) -> OrganizationMembership:
    """Dependency to verify user has admin access to an organization.

    Looks up all user's provider identities and checks if any have admin membership.

    Args:
        org_id: Organization UUID string from path parameter
        current_user: Authenticated user from get_current_user dependency

    Returns:
        OrganizationMembership if user is an admin

    Raises:
        HTTPException: 400 if org_id is not a valid UUID
        HTTPException: 403 if user doesn't have admin access to organization
    """
    organization_id = parse_uuid(org_id, "organization ID")

    # Use pre-loaded identities from get_current_user (no extra query needed)
    identity_ids = [identity.id for identity in current_user.identities]

    # Find membership for any of the user's identities
    app = get_current_app()
    with app.database.session() as db:
        membership = db_get_organization_memberships_by_identity(db, identity_ids, organization_id)

    if not membership:
        raise HTTPException(
            status_code=403,
            detail="You don't have access to this organization",
        )

    if membership.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only organization admins can perform this action",
        )

    return membership
