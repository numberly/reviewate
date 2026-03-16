"""Route handlers for GitHub sources management.

This module contains user-facing endpoints for managing GitHub App installations.
Webhook event handlers have been moved to /api/routers/webhooks/github/.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from api.context import get_current_app
from api.database import db_delete_organization_by_id
from api.database.organization import db_get_organization_by_id
from api.models import OrganizationMembership, User
from api.routers.auth.dependencies import get_current_user, require_github_enabled
from api.routers.organizations.dependencies import verify_organization_admin
from api.routers.sources.github.schemas import GitHubAppInstallUrl, UninstallResponse
from api.utils import parse_uuid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/github", tags=["Sources", "GitHub"])


@router.get(
    "/install-url",
    operation_id="get_github_install_url",
    name="get_github_install_url",
    summary="Get GitHub App installation URL",
    description="Returns the URL to install the GitHub App on an organization.",
    response_model=GitHubAppInstallUrl,
    status_code=200,
    dependencies=[Depends(require_github_enabled)],
)
async def get_github_install_url(
    current_user: User = Depends(get_current_user),
) -> GitHubAppInstallUrl:
    """Get the GitHub App installation URL.

    Args:
        current_user: Authenticated user from dependency

    Returns:
        GitHubAppInstallUrl with installation URL and app name
    """
    app = get_current_app()
    # Get GitHub App name from config
    if not app.github or not app.github.config.app:
        raise ValueError("GitHub plugin not configured")

    app_name = app.github.config.app.name
    # GitHub converts app names to lowercase and replaces spaces with hyphens
    app_slug = app_name.lower().replace(" ", "-")
    install_url = f"https://github.com/apps/{app_slug}/installations/new"

    return GitHubAppInstallUrl(url=install_url, app_name=app_name)


@router.delete(
    "/installations/{org_id}",
    operation_id="uninstall_github_app",
    name="uninstall_github_app",
    summary="Uninstall GitHub App",
    description=(
        "Uninstalls the GitHub App from both our database and the GitHub organization. "
        "This removes the app from GitHub and deletes all associated data from our system."
    ),
    response_model=UninstallResponse,
    status_code=200,
    dependencies=[Depends(require_github_enabled)],
)
async def uninstall_github_app(
    org_id: str,
    membership: OrganizationMembership = Depends(verify_organization_admin),
) -> UninstallResponse:
    """Uninstall GitHub App from both our database and GitHub organization.

    This endpoint performs two operations:
    1. Calls GitHub API to delete the installation (uninstalls app from org)
    2. Deletes the organization and all associated data from our database

    Args:
        org_id: Organization ID (UUID)
        membership: Admin membership from dependency

    Returns:
        UninstallResponse with success status

    Raises:
        HTTPException: 400 if invalid org_id format
        HTTPException: 404 if organization not found
        HTTPException: 403 if user lacks permission
        HTTPException: 500 if GitHub API call fails
    """
    app = get_current_app()

    with app.database.session() as db:
        org = db_get_organization_by_id(db, parse_uuid(org_id, "organization ID"))
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")

        await app.github.delete_installation(org.installation_id)
        db_delete_organization_by_id(db, org.id)

    logger.info(
        f"Successfully uninstalled GitHub App for organization {org.name} (installation {org.installation_id})"
    )

    return UninstallResponse(
        message=f"Successfully uninstalled GitHub App from {org.name}",
        success=True,
    )
