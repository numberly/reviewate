"""FastStream consumers for GitHub installation sync operations.

This module processes background jobs for syncing GitHub installations:
- Sync repositories when an installation is created
- Sync pull requests for each repository
- Sync organization members
"""

import logging
from datetime import datetime
from uuid import UUID

from faststream.redis import RedisRouter, StreamSub

from api.context import get_current_app
from api.database import (
    db_create_repository,
    db_create_repository_membership,
    db_get_identity_by_external_id,
    db_get_or_create_provider_identity,
    db_get_organization_by_installation_id,
    db_get_repository_by_external_id,
    db_sync_organization_membership,
    db_upsert_pull_request,
)
from api.plugins.faststream import get_faststream_broker
from api.plugins.faststream.config import STREAM_MAXLEN
from api.routers.webhooks.github.schemas import (
    GitHubSyncInstallationMessage,
    GitHubSyncMembersMessage,
    GitHubSyncRepositoryPRsMessage,
)
from api.sse.publishers import publish_pull_request_event, publish_repository_event

logger = logging.getLogger(__name__)

# FastStream router for GitHub sync events
router = RedisRouter()


@router.subscriber(
    stream=StreamSub(
        "reviewate.events.github.sync_installation", group="reviewate", consumer="worker-1"
    )
)
async def sync_installation_repositories(message: GitHubSyncInstallationMessage) -> None:
    """Sync all repositories for a GitHub App installation.

    This consumer runs in the background after an installation.created webhook.
    It fetches all repositories and creates them in the database, then queues
    PR sync for each repository.

    Args:
        message: Typed GitHub sync installation message
    """
    installation_id = message.installation_id
    sender_github_id = message.sender_github_id

    logger.info(f"Starting repository sync for installation {installation_id}")

    app = get_current_app()
    github_plugin = app.github

    # Phase 1: DB reads — find org and sender identity
    with app.database.session() as db:
        org = db_get_organization_by_installation_id(db, installation_id)
        if not org:
            logger.error(f"Organization not found for installation {installation_id}")
            return

        org_id = org.id

        sender_user_id = None
        if sender_github_id:
            sender_identity = db_get_identity_by_external_id(db, "github", sender_github_id)
            if sender_identity:
                sender_user_id = sender_identity.user_id

    # Phase 2: External API calls — no DB session held
    try:
        installation_token = await github_plugin.get_installation_access_token(installation_id)
        repos = await github_plugin.fetch_installation_repositories(installation_token)
    except Exception as e:
        logger.error(
            f"Failed to sync repositories for installation {installation_id}: {e}",
            exc_info=True,
        )
        return

    logger.info(f"Found {len(repos)} repositories for installation {installation_id}")

    # Phase 3: DB writes + fast publishes
    with app.database.session() as db:
        for repo_info in repos:
            external_repo_id = str(repo_info["id"])

            # Check if repository already exists
            existing_repo = db_get_repository_by_external_id(db, external_repo_id)
            if existing_repo:
                logger.debug(f"Repository {repo_info['name']} already exists, skipping")
                continue

            # Extract avatar URL from owner
            repo_avatar_url = repo_info.get("owner", {}).get("avatar_url")

            # Create repository
            repository = db_create_repository(
                db=db,
                organization_id=org_id,
                external_repo_id=external_repo_id,
                name=repo_info["name"],
                web_url=repo_info["html_url"],
                provider="github",
                provider_url="https://github.com",
                avatar_url=repo_avatar_url,
            )

            # Create repository membership for the installer if they have a linked user
            if sender_user_id:
                db_create_repository_membership(
                    db=db,
                    user_id=sender_user_id,
                    repository_id=repository.id,
                    role="admin",
                )

            logger.info(f"Created repository: {repo_info['name']} ({repository.id})")

            # Publish SSE event for repository creation
            try:
                await publish_repository_event(
                    organization_id=str(org_id),
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

            # Queue PR sync for this repository
            try:
                broker = get_faststream_broker()
                sync_message = GitHubSyncRepositoryPRsMessage(
                    repository_id=str(repository.id),
                    installation_id=installation_id,
                    owner=repo_info["owner"]["login"],
                    repo_name=repo_info["name"],
                )
                await broker.publish(
                    sync_message,
                    stream="reviewate.events.github.sync_repository_prs",
                    maxlen=STREAM_MAXLEN,
                )
                logger.debug(f"Queued PR sync for repository {repo_info['name']}")
            except Exception as e:
                logger.error(f"Failed to queue PR sync for {repo_info['name']}: {e}")

    logger.info(f"Successfully synced {len(repos)} repositories for installation {installation_id}")


@router.subscriber(
    stream=StreamSub(
        "reviewate.events.github.sync_repository_prs", group="reviewate", consumer="worker-1"
    )
)
async def sync_repository_pull_requests(message: GitHubSyncRepositoryPRsMessage) -> None:
    """Sync all pull requests for a repository.

    This consumer fetches all open PRs from GitHub and creates them in the database.

    Args:
        message: Typed GitHub sync repository PRs message
    """
    repository_id = message.repository_id
    installation_id = message.installation_id
    owner = message.owner
    repo_name = message.repo_name

    logger.info(f"Starting PR sync for repository {owner}/{repo_name}")

    app = get_current_app()
    github_plugin = app.github

    # Phase 1: External API calls — no DB session needed
    try:
        installation_token = await github_plugin.get_installation_access_token(installation_id)
        prs = await github_plugin.list_pull_requests(
            owner, repo_name, installation_token, state="open"
        )
    except Exception as e:
        logger.error(
            f"Failed to sync PRs for repository {owner}/{repo_name}: {e}",
            exc_info=True,
        )
        return

    logger.info(f"Found {len(prs)} open PRs for {owner}/{repo_name}")

    # Phase 2: DB writes
    created_count = 0
    with app.database.session() as db:
        for pr_info in prs:
            pr_number = pr_info["number"]

            # Get repository to find organization_id
            repo = db_get_repository_by_external_id(db, str(pr_info["base"]["repo"]["id"]))
            if not repo:
                logger.warning(f"Repository not found for PR #{pr_number}")
                continue

            # Parse the PR creation date from GitHub (ISO 8601 format)
            pr_created_at = None
            if pr_info.get("created_at"):
                pr_created_at = datetime.fromisoformat(pr_info["created_at"].replace("Z", "+00:00"))

            # Create or update PR record
            pr, created = db_upsert_pull_request(
                db=db,
                organization_id=repo.organization_id,
                repository_id=repository_id,
                pr_number=pr_number,
                external_pr_id=str(pr_info["id"]),
                title=pr_info["title"],
                author=pr_info["user"]["login"],
                state=pr_info["state"],
                head_branch=pr_info["head"]["ref"],
                base_branch=pr_info["base"]["ref"],
                head_sha=pr_info["head"]["sha"],
                pr_url=pr_info["html_url"],
                created_at=pr_created_at,
            )

            if created:
                created_count += 1
                logger.debug(f"Created PR #{pr_number}: {pr_info['title']}")
                await publish_pull_request_event(
                    pull_request_id=str(pr.id),
                    action="created",
                    organization_id=str(repo.organization_id),
                    repository_id=str(repository_id),
                    updated_at=pr.updated_at.isoformat() if pr.updated_at else None,
                )

    logger.info(f"Successfully synced {created_count}/{len(prs)} PRs for {owner}/{repo_name}")


@router.subscriber(
    stream=StreamSub("reviewate.events.github.sync_members", group="reviewate", consumer="worker-1")
)
async def sync_organization_members(message: GitHubSyncMembersMessage) -> None:
    """Sync all members for a GitHub organization.

    This consumer runs in the background after an installation.created webhook.
    It fetches all organization members from GitHub and creates ProviderIdentity
    and OrganizationMembership records for each member.

    Args:
        message: Typed GitHub sync members message
    """
    installation_id = message.installation_id
    organization_id = UUID(message.organization_id)
    org_name = message.org_name

    logger.info(f"Starting member sync for organization {org_name}")

    app = get_current_app()
    github_plugin = app.github

    # Phase 1: External API calls — no DB session needed
    try:
        installation_token = await github_plugin.get_installation_access_token(installation_id)
        members = await github_plugin.fetch_organization_members(installation_token, org_name)
    except Exception as e:
        logger.error(
            f"Failed to sync members for organization {org_name}: {e}",
            exc_info=True,
        )
        return

    logger.info(f"Found {len(members)} members for organization {org_name}")

    # Phase 2: API calls per member — collect roles without DB session
    member_roles = []
    for member_info in members:
        username = member_info.get("login")
        try:
            role = await github_plugin.get_organization_member_role(
                installation_token, org_name, username
            )
        except Exception as e:
            logger.warning(f"Failed to get role for member {username}: {e}")
            role = "member"
        member_roles.append((member_info, role))

    # Phase 3: Batch DB writes
    synced_count = 0
    with app.database.session() as db:
        for member_info, role in member_roles:
            external_id = str(member_info["id"])
            username = member_info.get("login")
            avatar_url = member_info.get("avatar_url")

            # Get or create provider identity for this member
            identity, _ = db_get_or_create_provider_identity(
                db=db,
                provider="github",
                external_id=external_id,
                username=username,
                avatar_url=avatar_url,
            )

            # Create or update organization membership
            db_sync_organization_membership(
                db=db,
                provider_identity_id=identity.id,
                organization_id=organization_id,
                role=role,
            )

            synced_count += 1
            logger.debug(f"Synced member {username} with role {role}")

    logger.info(f"Successfully synced {synced_count} members for organization {org_name}")
