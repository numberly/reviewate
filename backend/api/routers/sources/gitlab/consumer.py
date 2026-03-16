"""FastStream consumers for GitLab source sync operations.

This module processes background jobs for syncing GitLab sources:
- Sync repositories when a group token is added
- Sync merge requests for each repository
- Sync group members
"""

import logging
from datetime import datetime
from uuid import UUID

from faststream.redis import RedisRouter, StreamSub

from api.context import get_current_app
from api.database import (
    db_create_repository,
    db_create_repository_membership,
    db_get_or_create_provider_identity,
    db_get_organization_by_id,
    db_get_repository_by_external_id,
    db_get_repository_by_id,
    db_sync_organization_membership,
    db_upsert_pull_request,
)
from api.plugins.faststream import get_faststream_broker
from api.plugins.faststream.config import STREAM_MAXLEN
from api.routers.sources.gitlab.schemas import (
    GitLabSyncGroupMessage,
    GitLabSyncGroupRepositoriesMessage,
    GitLabSyncMembersMessage,
    GitLabSyncRepositoryMRsMessage,
)
from api.security import get_encryptor
from api.sse.publishers import publish_pull_request_event, publish_repository_event

logger = logging.getLogger(__name__)

# FastStream router for GitLab sync events
router = RedisRouter()


@router.subscriber(
    stream=StreamSub("reviewate.events.gitlab.sync_group", group="reviewate", consumer="worker-1")
)
async def sync_group_merge_requests(message: GitLabSyncGroupMessage) -> None:
    """Sync all merge requests for all repositories in a GitLab group.

    This consumer runs in the background after a group token is added.
    It queues MR sync for each repository.

    Args:
        message: Typed GitLab sync group message
    """
    organization_id = message.organization_id
    repository_ids = message.repository_ids

    # Queue MR sync for each repository
    try:
        broker = get_faststream_broker()
        for repo_id in repository_ids:
            sync_message = GitLabSyncRepositoryMRsMessage(
                repository_id=repo_id,
                organization_id=organization_id,
            )
            await broker.publish(
                sync_message,
                stream="reviewate.events.gitlab.sync_repository_mrs",
                maxlen=STREAM_MAXLEN,
            )
            logger.debug(f"Queued MR sync for repository {repo_id}")
    except Exception as e:
        logger.error(f"Failed to queue MR sync jobs: {e}", exc_info=True)


@router.subscriber(
    stream=StreamSub(
        "reviewate.events.gitlab.sync_group_repositories", group="reviewate", consumer="worker-1"
    )
)
async def sync_group_repositories(message: GitLabSyncGroupRepositoriesMessage) -> None:
    """Sync all repositories for a GitLab group.

    This consumer runs in the background after a group token is added.
    It fetches all group projects from GitLab API, creates repositories
    in the database, and queues MR sync for each repository.

    Args:
        message: Typed GitLab sync group repositories message
    """
    organization_id = message.organization_id
    group_id = message.group_id
    user_id = message.user_id

    logger.info(f"Starting repository sync for GitLab group {group_id}")

    app = get_current_app()
    gitlab_plugin = app.gitlab

    # Phase 1: DB reads — get org and decrypt token
    with app.database.session() as db:
        org = db_get_organization_by_id(db, organization_id)
        if not org:
            logger.error(f"Organization {organization_id} not found")
            return

        # Token priority: message token (subgroup) > org token (root group)
        encrypted_token = message.encrypted_token or org.gitlab_access_token_encrypted
        if not encrypted_token:
            logger.error(f"No GitLab access token found for organization {organization_id}")
            return

        encryptor = get_encryptor()
        access_token = encryptor.decrypt(encrypted_token)
        provider_url = org.provider_url or "https://gitlab.com"

    # Phase 2: External API calls — no DB session held
    try:
        projects = await gitlab_plugin.fetch_group_projects(access_token, group_id)
    except Exception as e:
        logger.error(
            f"Failed to fetch projects for group {group_id}: {e}",
            exc_info=True,
        )
        return

    logger.info(f"Found {len(projects)} projects for group {group_id}")

    # Determine per-repo token: subgroup tokens go on each repo, root tokens don't
    repo_token = encrypted_token if message.store_token_on_repos else None

    # Phase 3: DB writes + SSE events + queue MR sync per repo
    with app.database.session() as db:
        for project_info in projects:
            external_repo_id = str(project_info["id"])

            existing_repo = db_get_repository_by_external_id(db, external_repo_id)
            if existing_repo:
                logger.debug(f"Repository {project_info['name']} already exists, skipping")
                continue

            project_avatar_url = project_info.get("avatar_url") or project_info.get(
                "namespace", {}
            ).get("avatar_url")

            repository = db_create_repository(
                db=db,
                organization_id=organization_id,
                external_repo_id=external_repo_id,
                name=project_info["name"],
                web_url=project_info["web_url"],
                provider="gitlab",
                provider_url=provider_url,
                gitlab_access_token_encrypted=repo_token,
                avatar_url=project_avatar_url,
            )

            db_create_repository_membership(
                db=db,
                user_id=user_id,
                repository_id=repository.id,
                role="admin",
            )

            logger.info(f"Created repository: {project_info['name']} ({repository.id})")

            # Publish SSE event for repository creation
            try:
                await publish_repository_event(
                    organization_id=str(organization_id),
                    action="created",
                    repository={
                        "id": str(repository.id),
                        "name": repository.name,
                        "external_repo_id": repository.external_repo_id,
                        "web_url": repository.web_url,
                        "provider": repository.provider,
                        "created_at": repository.created_at.isoformat(),
                        "updated_at": repository.updated_at.isoformat(),
                    },
                )
            except Exception as e:
                logger.error(f"Failed to publish repository SSE event: {e}", exc_info=True)

            # Queue MR sync for this repository
            try:
                broker = get_faststream_broker()
                sync_message = GitLabSyncRepositoryMRsMessage(
                    repository_id=str(repository.id),
                    organization_id=organization_id,
                )
                await broker.publish(
                    sync_message,
                    stream="reviewate.events.gitlab.sync_repository_mrs",
                    maxlen=STREAM_MAXLEN,
                )
                logger.debug(f"Queued MR sync for repository {project_info['name']}")
            except Exception as e:
                logger.error(f"Failed to queue MR sync for {project_info['name']}: {e}")

    logger.info(f"Successfully synced repositories for group {group_id}")


@router.subscriber(
    stream=StreamSub(
        "reviewate.events.gitlab.sync_repository_mrs", group="reviewate", consumer="worker-1"
    )
)
async def sync_repository_merge_requests(message: GitLabSyncRepositoryMRsMessage) -> None:
    """Sync all merge requests for a single GitLab repository.

    This consumer fetches all merge requests from GitLab API and creates
    them in the database.

    Args:
        message: Typed GitLab sync repository MRs message
    """
    repository_id = message.repository_id
    organization_id = message.organization_id

    app = get_current_app()
    gitlab_plugin = app.gitlab

    # Phase 1: DB reads — get repository, org, and decrypt token
    with app.database.session() as db:
        repository = db_get_repository_by_id(db, repository_id)
        if not repository:
            logger.error(f"Repository {repository_id} not found")
            return

        org = db_get_organization_by_id(db, organization_id)
        if not org:
            logger.error(f"Organization {organization_id} not found")
            return

        if not repository.gitlab_access_token_encrypted and not org.gitlab_access_token_encrypted:
            logger.error(f"No GitLab access token found for repository {repository_id}")
            return

        encryptor = get_encryptor()
        access_token = encryptor.decrypt(
            repository.gitlab_access_token_encrypted or org.gitlab_access_token_encrypted
        )
        external_repo_id = repository.external_repo_id
        repo_name = repository.name

    # Phase 2: External API calls — paginated fetch, no DB session held
    try:
        mrs = await gitlab_plugin.list_merge_requests(
            project_id=external_repo_id, state="opened", access_token=access_token
        )
    except Exception as e:
        logger.error(
            f"Failed to sync merge requests for repository {repository_id}: {e}",
            exc_info=True,
        )
        return

    # Phase 3: DB writes
    created_count = 0
    with app.database.session() as db:
        for mr_info in mrs:
            mr_number = mr_info["iid"]

            # Parse the MR creation date from GitLab (ISO 8601 format)
            mr_created_at = None
            if mr_info.get("created_at"):
                mr_created_at = datetime.fromisoformat(mr_info["created_at"].replace("Z", "+00:00"))

            # Create or update MR record
            pr, created = db_upsert_pull_request(
                db=db,
                organization_id=organization_id,
                repository_id=repository_id,
                pr_number=mr_number,
                external_pr_id=str(mr_info["id"]),
                title=mr_info["title"],
                author=mr_info["author"]["username"],
                state=mr_info["state"],
                head_branch=mr_info["source_branch"],
                base_branch=mr_info["target_branch"],
                head_sha=mr_info["sha"],
                pr_url=mr_info["web_url"],
                created_at=mr_created_at,
            )

            if created:
                created_count += 1
                await publish_pull_request_event(
                    pull_request_id=str(pr.id),
                    action="created",
                    organization_id=str(organization_id),
                    repository_id=str(repository_id),
                    updated_at=pr.updated_at.isoformat() if pr.updated_at else None,
                )

    if created_count > 0:
        logger.info(f"Synced {created_count} MRs for {repo_name}")


@router.subscriber(
    stream=StreamSub("reviewate.events.gitlab.sync_members", group="reviewate", consumer="worker-1")
)
async def sync_group_members(message: GitLabSyncMembersMessage) -> None:
    """Sync all members for a GitLab group.

    This consumer runs in the background after a group token is added.
    It fetches all group members from GitLab API and creates ProviderIdentity
    and OrganizationMembership records for each member.

    Args:
        message: Typed GitLab sync members message
    """
    organization_id = UUID(message.organization_id)
    group_id = message.group_id

    app = get_current_app()
    gitlab_plugin = app.gitlab

    # Phase 1: DB reads — get org and decrypt token
    with app.database.session() as db:
        org = db_get_organization_by_id(db, organization_id)
        if not org:
            logger.error(f"Organization {organization_id} not found")
            return

        # Token priority: message token (subgroup) > org token (root group)
        encrypted_token = message.encrypted_token or org.gitlab_access_token_encrypted
        if not encrypted_token:
            logger.error(f"No GitLab access token found for organization {organization_id}")
            return

        encryptor = get_encryptor()
        access_token = encryptor.decrypt(encrypted_token)

    # Phase 2: External API call — fetch members, no DB session held
    try:
        members = await gitlab_plugin.fetch_group_members(access_token, group_id)
    except Exception as e:
        logger.error(
            f"Failed to sync members for group {group_id}: {e}",
            exc_info=True,
        )
        return

    # Phase 3: Batch DB writes
    with app.database.session() as db:
        for member_info in members:
            external_id = str(member_info["id"])
            username = member_info.get("username")
            avatar_url = member_info.get("avatar_url")
            access_level = member_info.get("access_level", 10)

            # Get or create provider identity for this member
            identity, _ = db_get_or_create_provider_identity(
                db=db,
                provider="gitlab",
                external_id=external_id,
                username=username,
                avatar_url=avatar_url,
            )

            # Map GitLab access level to Reviewate role
            role = gitlab_plugin.map_access_level_to_role(access_level)

            # Create or update organization membership
            db_sync_organization_membership(
                db=db,
                provider_identity_id=identity.id,
                organization_id=organization_id,
                role=role,
            )

    logger.info(f"Synced {len(members)} members for group {group_id}")
