"""Route handlers for GitLab sources management."""

import asyncio
import logging
from dataclasses import dataclass
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError

from api.context import get_current_app
from api.database import (
    db_create_organization,
    db_create_repository,
    db_create_repository_membership,
    db_delete_organization_by_id,
    db_get_organization_by_external_id,
    db_get_repository_by_external_id,
    db_sync_organization_membership,
    db_update_organization_settings,
)
from api.database.organization import db_get_organization_by_id
from api.models import OrganizationMembership, User
from api.plugins.faststream import get_faststream_broker
from api.plugins.faststream.config import STREAM_MAXLEN
from api.plugins.gitlab.plugin import GitLabPlugin
from api.plugins.gitlab.schemas import GitlabTokenType
from api.routers.auth.dependencies import get_current_user, require_gitlab_enabled
from api.routers.organizations.dependencies import verify_organization_admin
from api.routers.sources.schemas import DeleteOrganizationResponse
from api.security import get_encryptor
from api.utils import parse_uuid

from .schemas import (
    AddGitLabSourceRequest,
    GitLabSourceResponse,
    GitLabSyncGroupRepositoriesMessage,
    GitLabSyncMembersMessage,
    GitLabSyncRepositoryMRsMessage,
)
from .utils import extract_group_id_from_username, extract_project_id_from_username

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gitlab", tags=["Sources", "GitLab"])


@dataclass
class _GitLabSourceContext:
    """Shared context for GitLab source creation handlers."""

    gitlab_plugin: GitLabPlugin
    token_data: dict
    encrypted_token: str
    access_token: str
    provider_url: str
    user_id: UUID
    user_email: str | None
    gitlab_identity_id: UUID
    gitlab_external_id: str


@router.post(
    "",
    operation_id="add_gitlab_source",
    response_model=GitLabSourceResponse,
    dependencies=[Depends(require_gitlab_enabled)],
)
async def add_gitlab_source(
    request: AddGitLabSourceRequest,
    current_user: User = Depends(get_current_user),
) -> GitLabSourceResponse:
    """Add a GitLab source (group or project) by providing an Access Token.

    This endpoint:
    1. Verifies the GitLab token is valid
    2. Determines if it's a group or project token
    3. Creates Organization (group token) or Repository (project token)
    4. Stores the encrypted token
    5. Creates membership for the current user

    Args:
        request: Request containing GitLab access token
        current_user: Authenticated user

    Returns:
        GitLabSourceResponse with created source information

    Raises:
        HTTPException: If token is invalid or API calls fail
    """
    app = get_current_app()
    gitlab_plugin = app.gitlab

    # Verify the token (external API call — no session held)
    try:
        token_data = await gitlab_plugin.verify_token(
            request.access_token, provider_url=request.provider_url
        )
    except HTTPException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=f"Failed to verify GitLab token: {e.detail}",
        ) from e

    # Determine token type
    token_type = gitlab_plugin.get_token_type(token_data)
    logger.debug(
        f"Adding GitLab source: token_type={token_type}, "
        f"provider_url={request.provider_url}, user={current_user.email}"
    )

    if token_type not in [GitlabTokenType.GROUP_ACCESS_TOKEN, GitlabTokenType.PROJECT_ACCESS_TOKEN]:  # type: ignore[attr-defined]
        raise HTTPException(
            status_code=400,
            detail="Token must be a group or project access token.",
        )

    # Extract identity info from pre-loaded user (no session needed)
    gitlab_identity = current_user.get_identity("gitlab")
    if not gitlab_identity:
        raise HTTPException(
            status_code=400,
            detail="Please link your GitLab account first. Go to Settings and connect your GitLab account, then try adding this source again.",
        )

    # Build shared context
    encryptor = get_encryptor()
    ctx = _GitLabSourceContext(
        gitlab_plugin=gitlab_plugin,
        token_data=token_data,
        encrypted_token=encryptor.encrypt(request.access_token),
        access_token=request.access_token,
        provider_url=request.provider_url,
        user_id=current_user.id,
        user_email=current_user.email,
        gitlab_identity_id=gitlab_identity.id,
        gitlab_external_id=gitlab_identity.external_id,
    )

    # Route to appropriate handler based on token type
    if token_type == GitlabTokenType.GROUP_ACCESS_TOKEN:  # type: ignore[attr-defined]
        return await _handle_group_token(ctx)
    else:  # PROJECT_ACCESS_TOKEN
        return await _handle_project_token(ctx)


async def _handle_group_token(ctx: _GitLabSourceContext) -> GitLabSourceResponse:
    """Handle group access token to create organization and all its repositories.

    Subgroup tokens create the org at the root (top-level) group.
    The subgroup token is stored on repos, not the org.
    If a root group token arrives later, it upserts onto the existing org.
    """
    app = get_current_app()

    # Phase 1 (no session): External API calls (parallel)
    group_id = extract_group_id_from_username(ctx.token_data["username"])

    group_info, user_role = await asyncio.gather(
        ctx.gitlab_plugin.fetch_group(ctx.access_token, group_id),
        ctx.gitlab_plugin.determine_user_role_in_group(
            access_token=ctx.access_token,
            group_id=group_id,
            gitlab_user_id=ctx.gitlab_external_id,
            user_email=ctx.user_email,
        ),
    )

    if user_role != "admin":
        raise HTTPException(
            status_code=403,
            detail="You must be at least a Maintainer of this GitLab group to add it. Please ask a group Owner or Maintainer to add this source.",
        )

    # Detect subgroup: if parent_id is set, resolve root group
    is_subgroup = group_info.get("parent_id") is not None
    if is_subgroup:
        root_group = await ctx.gitlab_plugin.resolve_root_group(ctx.access_token, group_id)
    else:
        root_group = group_info

    root_group_id = str(root_group["id"])

    # Phase 2 (session): Create or upsert organization and membership
    with app.database.session() as db:
        organization = db_get_organization_by_external_id(
            db=db,
            external_org_id=root_group_id,
            provider="gitlab",
        )

        if organization:
            # Org exists — upsert token only if this is a root group token
            if not is_subgroup:
                db_update_organization_settings(
                    db=db,
                    organization_id=organization.id,
                    gitlab_access_token_encrypted=ctx.encrypted_token,
                )
        else:
            # Create new org — store token only if root group token
            organization = db_create_organization(
                db=db,
                name=root_group["name"],
                external_org_id=root_group_id,
                installation_id=f"gitlab-group-{root_group_id}",
                provider="gitlab",
                provider_url=ctx.provider_url,
                gitlab_access_token_encrypted=ctx.encrypted_token if not is_subgroup else None,
                avatar_url=root_group.get("avatar_url"),
            )

        db_sync_organization_membership(
            db=db,
            provider_identity_id=ctx.gitlab_identity_id,
            organization_id=organization.id,
            role=user_role,
        )

        org_id = str(organization.id)
        org_name = organization.name
        org_created_at = organization.created_at

    # Phase 3: Queue background syncs (outside DB session)
    broker = get_faststream_broker()

    # Sync repos for the group the token actually belongs to
    repo_sync_msg = GitLabSyncGroupRepositoriesMessage(
        organization_id=org_id,
        group_id=group_id,
        user_id=str(ctx.user_id),
    )
    if is_subgroup:
        repo_sync_msg.encrypted_token = ctx.encrypted_token
        repo_sync_msg.store_token_on_repos = True

    try:
        await broker.publish(
            repo_sync_msg,
            stream="reviewate.events.gitlab.sync_group_repositories",
            maxlen=STREAM_MAXLEN,
        )
    except Exception as e:
        logger.error(f"Failed to queue repo sync for group {org_name}: {e}")

    member_sync_msg = GitLabSyncMembersMessage(
        organization_id=org_id,
        group_id=group_id,
    )
    if is_subgroup:
        member_sync_msg.encrypted_token = ctx.encrypted_token

    try:
        await broker.publish(
            member_sync_msg,
            stream="reviewate.events.gitlab.sync_members",
            maxlen=STREAM_MAXLEN,
        )
    except Exception as e:
        logger.error(f"Failed to queue member sync for group {org_name}: {e}")

    return GitLabSourceResponse(
        source_type="group",
        source_id=org_id,
        source_name=org_name,
        membership_created=True,
        created_at=org_created_at,
    )


async def _handle_project_token(ctx: _GitLabSourceContext) -> GitLabSourceResponse:
    """Handle project access token to create repository."""
    app = get_current_app()

    # Phase 1 (no session): External API calls (parallel)
    project_id = extract_project_id_from_username(ctx.token_data["username"])

    project_info, user_org_role = await asyncio.gather(
        ctx.gitlab_plugin.fetch_project(ctx.access_token, project_id),
        ctx.gitlab_plugin.determine_user_role_in_project(
            access_token=ctx.access_token,
            project_id=project_id,
            gitlab_user_id=ctx.gitlab_external_id,
            user_email=ctx.user_email,
        ),
    )

    if user_org_role != "admin":
        raise HTTPException(
            status_code=403,
            detail="You must be at least a Maintainer of this GitLab project to add it. Please ask a project Maintainer or Owner to add this source.",
        )

    # Resolve root group — namespace may be a subgroup
    namespace = project_info["namespace"]
    if namespace.get("parent_id") is not None:
        root_group = await ctx.gitlab_plugin.resolve_root_group(
            ctx.access_token, str(namespace["id"])
        )
    else:
        root_group = namespace

    root_group_id = str(root_group["id"])

    # Phase 2 (session): Create org, membership, repository, queue sync
    with app.database.session() as db:
        organization = db_get_organization_by_external_id(
            db=db,
            external_org_id=root_group_id,
            provider="gitlab",
        )

        if not organization:
            organization = db_create_organization(
                db=db,
                name=root_group.get("name") or namespace["name"],
                external_org_id=root_group_id,
                installation_id=f"gitlab-group-{root_group_id}",
                provider="gitlab",
                provider_url=ctx.provider_url,
                avatar_url=root_group.get("avatar_url"),
            )

        db_sync_organization_membership(
            db=db,
            provider_identity_id=ctx.gitlab_identity_id,
            organization_id=organization.id,
            role=user_org_role,
        )

        try:
            project_avatar_url = project_info.get("avatar_url") or project_info.get(
                "namespace", {}
            ).get("avatar_url")

            repository = db_create_repository(
                db=db,
                organization_id=organization.id,
                external_repo_id=str(project_info["id"]),
                name=project_info["name"],
                web_url=project_info["web_url"],
                provider="gitlab",
                provider_url=ctx.provider_url,
                gitlab_access_token_encrypted=ctx.encrypted_token,
                avatar_url=project_avatar_url,
            )

            db_create_repository_membership(
                db=db,
                user_id=ctx.user_id,
                repository_id=repository.id,
                role=user_org_role,
            )

        except IntegrityError as e:
            db.rollback()
            if "external_repo_id" in str(e.orig) or "duplicate" in str(e.orig).lower():
                raise HTTPException(
                    status_code=409,
                    detail=f"This GitLab project has already been added. Project: {project_info['name']}",
                ) from e
            raise

        # Re-fetch to get final state
        repository = db_get_repository_by_external_id(db, str(project_info["id"]))

        # Queue background sync
        try:
            broker = get_faststream_broker()
            sync_message = GitLabSyncRepositoryMRsMessage(
                repository_id=str(repository.id),
                organization_id=str(organization.id),
            )
            await broker.publish(
                sync_message,
                stream="reviewate.events.gitlab.sync_repository_mrs",
                maxlen=STREAM_MAXLEN,
            )
        except Exception as e:
            logger.error(f"Failed to queue MR sync for project {project_info['name']}: {e}")

        return GitLabSourceResponse(
            source_type="project",
            source_id=str(repository.id) if repository else str(organization.id),
            source_name=repository.name if repository else organization.name,
            membership_created=True,
            created_at=repository.created_at if repository else organization.created_at,
        )


@router.delete(
    "/organizations/{org_id}",
    operation_id="delete_gitlab_organization",
    name="delete_gitlab_organization",
    summary="Delete GitLab organization",
    description=(
        "Deletes a GitLab organization (group) and all associated data from the system. "
        "This removes the organization, repositories, and memberships from our database."
    ),
    response_model=DeleteOrganizationResponse,
    status_code=200,
)
async def delete_gitlab_organization(
    org_id: str,
    membership: OrganizationMembership = Depends(verify_organization_admin),
) -> DeleteOrganizationResponse:
    """Delete a GitLab organization from the database.

    This endpoint deletes the organization and all associated data (repositories,
    memberships, pull requests) from our database. It does not affect GitLab itself.

    Args:
        org_id: Organization ID (UUID)
        membership: Admin membership from dependency

    Returns:
        DeleteOrganizationResponse with success message

    Raises:
        HTTPException: 400 if invalid org_id format
        HTTPException: 404 if organization not found
        HTTPException: 403 if user lacks permission
    """
    app = get_current_app()

    with app.database.session() as db:
        org = db_get_organization_by_id(db, parse_uuid(org_id, "organization ID"))
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")

        # Verify it's a GitLab organization
        if org.provider != "gitlab":
            raise HTTPException(
                status_code=400,
                detail="This endpoint is only for GitLab organizations",
            )

        org_name = org.name

        # Delete from database (cascade deletes repos, memberships, etc.)
        db_delete_organization_by_id(db, org.id)

    logger.info(f"Successfully deleted GitLab organization {org_name} (ID: {org_id})")

    return DeleteOrganizationResponse(
        message=f"Successfully deleted GitLab organization {org_name}",
        organization_id=org_id,
    )
