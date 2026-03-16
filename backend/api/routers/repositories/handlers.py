"""API route handlers for repositories endpoints."""

import asyncio
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from api.database import (
    db_delete_repository_by_id,
    db_get_repositories_by_organization,
    db_reset_repository_settings,
    db_update_repository_settings,
    get_session,
)
from api.models import OrganizationMembership, Repository
from api.routers.base_schema import ListGenericResponse
from api.routers.organizations.dependencies import verify_organization_access
from api.sse import make_sse_event

from . import consumer as repo_consumer
from .dependencies import verify_repository_access, verify_repository_admin
from .schemas import (
    DeleteRepositoryResponse,
    RepositoryListItem,
    RepositorySettings,
    RepositorySettingsUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Repositories"])


@router.get(
    "/organizations/{org_id}/repositories",
    operation_id="list_repositories",
    name="list_organization_repositories",
    summary="List organization repositories",
    description="Lists all repositories that are registered for a specific organization.",
    response_model=ListGenericResponse[RepositoryListItem],
    status_code=200,
)
async def list_organization_repositories(
    membership: OrganizationMembership = Depends(verify_organization_access),
    db: Session = Depends(get_session),
) -> ListGenericResponse[RepositoryListItem]:
    """List all repositories for an organization.

    Args:
        membership: Organization membership from dependency (verifies access and extracts org_id)
        db: Database session

    Returns:
        ListGenericResponse with organization's repositories

    Raises:
        HTTPException: 403 if user doesn't have access to organization (handled by dependency)
    """
    # Query repositories for this organization
    repositories = db_get_repositories_by_organization(db, membership.organization_id)

    # Convert to response schema
    repo_items = [RepositoryListItem.model_validate(repo) for repo in repositories]

    return ListGenericResponse(objects=repo_items)


@router.get(
    "/organizations/{org_id}/repositories/stream",
    operation_id="stream_repositories",
    name="stream_repositories",
    summary="Stream repository updates",
    description="Server-Sent Events stream for real-time repository updates for an organization.",
    status_code=200,
)
async def stream_repositories(
    membership: OrganizationMembership = Depends(verify_organization_access),
) -> EventSourceResponse:
    """Stream real-time repository updates for an organization.

    This endpoint provides an SSE stream that pushes updates when:
    - New repositories are added (synced from GitHub/GitLab)
    - Repositories are removed
    - Repository metadata changes

    The stream remains open and pushes events as they occur.

    Args:
        membership: Organization membership from dependency (verifies access)

    Returns:
        EventSourceResponse with repository update events
    """
    organization_id = str(membership.organization_id)

    async def event_generator() -> AsyncGenerator[dict[str, str]]:
        """Generate SSE events for repository updates."""
        # Register client for updates
        queue = repo_consumer.register_client(organization_id)

        try:
            # Send initial connection event
            yield make_sse_event(
                "connected",
                {"organization_id": organization_id, "message": "Streaming repository updates"},
            )

            # Stream events from queue with timeout to allow graceful shutdown
            while True:
                try:
                    event_data = await asyncio.wait_for(queue.get(), timeout=30.0)
                except TimeoutError:
                    # Send keepalive to prevent connection timeout, allows CancelledError to propagate
                    yield make_sse_event("keepalive", {})
                    continue

                # Check for shutdown signal
                if event_data.get("__sse_shutdown__"):
                    logger.debug(f"SSE shutdown signal received for org {organization_id}")
                    break

                yield make_sse_event("repo_update", event_data)

        except asyncio.CancelledError:
            logger.debug(
                f"SSE client disconnected for organization {organization_id} (repositories)"
            )
            raise
        except Exception as e:
            logger.error(
                f"SSE error for organization {organization_id} (repositories): {e}", exc_info=True
            )
            yield make_sse_event("error", {"error": str(e)})
        finally:
            repo_consumer.unregister_client(organization_id, queue)

    return EventSourceResponse(event_generator())


@router.delete(
    "/repositories/{repo_id}",
    operation_id="delete_repository",
    name="delete_repository",
    summary="Delete repository",
    description="Deletes a repository from the organization.",
    response_model=DeleteRepositoryResponse,
    status_code=200,
)
async def delete_repository(
    access: tuple[Repository, OrganizationMembership] = Depends(verify_repository_access),
    db: Session = Depends(get_session),
) -> DeleteRepositoryResponse:
    """Delete a repository. Only removes it from our database."""
    repository, _ = access

    deleted = db_delete_repository_by_id(db, repository.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Repository not found")

    return DeleteRepositoryResponse(
        message="Repository deleted successfully",
        repository_id=str(repository.id),
    )


@router.get(
    "/repositories/{repo_id}/settings",
    operation_id="get_repository_settings",
    name="get_repository_settings",
    summary="Get repository settings",
    description="Get the raw settings for a repository (before inheritance from organization).",
    response_model=RepositorySettings,
    status_code=200,
)
async def get_repository_settings(
    access: tuple[Repository, OrganizationMembership] = Depends(verify_repository_access),
) -> RepositorySettings:
    """Get raw repository settings (null means inherited from org)."""
    repository, _ = access
    return RepositorySettings.model_validate(repository)


@router.patch(
    "/repositories/{repo_id}/settings",
    operation_id="update_repository_settings",
    name="update_repository_settings",
    summary="Update repository settings",
    description="Update settings for a repository. Pass null to clear overrides and inherit from organization.",
    response_model=RepositorySettings,
    status_code=200,
)
async def update_repository_settings(
    settings: RepositorySettingsUpdate,
    access: tuple[Repository, OrganizationMembership] = Depends(verify_repository_admin),
    db: Session = Depends(get_session),
) -> RepositorySettings:
    """Update repository settings. Requires org admin role."""
    repository, _ = access

    update_kwargs: dict[str, str | bool | None] = {}
    if settings.automatic_review_trigger is not None:
        update_kwargs["automatic_review_trigger"] = settings.automatic_review_trigger.value
    if settings.automatic_summary_trigger is not None:
        update_kwargs["automatic_summary_trigger"] = settings.automatic_summary_trigger.value

    repository = db_update_repository_settings(
        db,
        repository.id,
        **update_kwargs,
    )
    return RepositorySettings.model_validate(repository)


@router.delete(
    "/repositories/{repo_id}/settings",
    operation_id="reset_repository_settings",
    name="reset_repository_settings",
    summary="Reset repository settings",
    description="Reset repository settings to inherit from organization. Requires admin role.",
    response_model=RepositorySettings,
    status_code=200,
)
async def reset_repository_settings(
    access: tuple[Repository, OrganizationMembership] = Depends(verify_repository_admin),
    db: Session = Depends(get_session),
) -> RepositorySettings:
    """Reset repository settings to inherit from organization. Requires org admin role."""
    repository, _ = access
    repository = db_reset_repository_settings(db, repository.id)
    return RepositorySettings.model_validate(repository)
