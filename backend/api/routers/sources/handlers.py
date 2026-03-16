"""Sources router for managing GitLab/GitHub integrations."""

from fastapi import APIRouter, Depends

from api.context import get_current_app
from api.database import db_get_user_organizations_with_roles
from api.models import User
from api.routers.auth import get_current_user
from api.routers.base_schema import ListGenericResponse

from . import github, gitlab
from .schemas import OrganizationListItem

# Create main sources router
router = APIRouter(prefix="/sources", tags=["Sources"])


# Platform-agnostic endpoints
@router.get(
    "",
    operation_id="list_sources",
    name="list_sources",
    summary="List user's sources",
    description="Lists all sources/organizations the authenticated user is a member of (from all platforms).",
    response_model=ListGenericResponse[OrganizationListItem],
    status_code=200,
)
async def list_sources(
    current_user: User = Depends(get_current_user),
) -> ListGenericResponse[OrganizationListItem]:
    """List all sources for the current user across all platforms.

    A source represents an organization from GitHub, GitLab, or other platforms.

    Args:
        current_user: Authenticated user from dependency

    Returns:
        ListGenericResponse with user's sources from GitHub, GitLab, etc.
    """
    identity_ids = [identity.id for identity in current_user.identities]
    if not identity_ids:
        return ListGenericResponse(objects=[])

    app = get_current_app()
    with app.database.session() as db:
        results = db_get_user_organizations_with_roles(db, identity_ids)

    org_items = [
        OrganizationListItem(
            id=org.id,
            name=org.name,
            external_org_id=org.external_org_id,
            installation_id=org.installation_id,
            provider=org.provider,
            avatar_url=org.avatar_url,
            created_at=org.created_at,
            role=role,
        )
        for org, role in results
    ]

    return ListGenericResponse(objects=org_items)


# Include platform-specific routers
router.include_router(github.router, tags=["GitHub"])
router.include_router(gitlab.router, tags=["GitLab"])

__all__ = ["router"]
