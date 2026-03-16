"""GitHub installation webhook handlers."""

import logging

from fastapi import HTTPException
from sqlalchemy.orm import Session

from api.database import (
    db_create_organization,
    db_create_organization_membership,
    db_create_repository,
    db_create_repository_membership,
    db_delete_organization,
    db_delete_repository,
    db_get_identity_by_external_id,
    db_get_or_create_provider_identity,
    db_get_organization_by_installation_id,
    db_get_repository_by_external_id,
)
from api.plugins.faststream import get_faststream_broker
from api.plugins.faststream.config import STREAM_MAXLEN
from api.sse.publishers import (
    publish_organization_event,
    publish_repository_event,
)

from ..utils import WebhookResponse
from .schemas import (
    GitHubAppInstallationEvent,
    GitHubAppInstallationRepositoriesEvent,
    GitHubSyncInstallationMessage,
    GitHubSyncMembersMessage,
)

logger = logging.getLogger(__name__)


async def handle_installation_created(
    event: GitHubAppInstallationEvent,
    db: Session,
) -> WebhookResponse:
    """Handle installation.created event - Create organization and all its repositories.

    Args:
        event: GitHub App installation event
        db: Database session

    Returns:
        WebhookResponse confirmation
    """
    installation = event.installation
    sender = event.sender

    # Extract organization data from installation object
    if "account" not in installation:
        raise HTTPException(status_code=400, detail="Missing account data in installation payload")

    account = installation["account"]
    installation_id = str(installation["id"])
    external_org_id = str(account["id"])
    org_name = account["login"]

    # Check if organization already exists
    existing_org = db_get_organization_by_installation_id(db, installation_id)

    if existing_org:
        return WebhookResponse(
            message=f"Organization {org_name} already exists",
            processed=True,
        )

    # Extract avatar URL from account data
    avatar_url = account.get("avatar_url")

    # Create new organization
    organization = db_create_organization(
        db=db,
        name=org_name,
        external_org_id=external_org_id,
        installation_id=installation_id,
        provider="github",
        provider_url="https://github.com",
        avatar_url=avatar_url,
    )

    # Get or create provider identity for the sender and add them as admin
    sender_github_id = str(sender["id"])
    sender_identity, _ = db_get_or_create_provider_identity(
        db=db,
        provider="github",
        external_id=sender_github_id,
        username=sender.get("login"),
        avatar_url=sender.get("avatar_url"),
    )

    # Create organization membership for sender
    db_create_organization_membership(
        db=db,
        provider_identity_id=sender_identity.id,
        organization_id=organization.id,
        role="admin",
    )

    # Publish SSE event for organization creation if sender has a linked user
    if sender_identity.user_id:
        try:
            await publish_organization_event(
                user_id=str(sender_identity.user_id),
                action="created",
                organization={
                    "id": str(organization.id),
                    "name": organization.name,
                    "provider": organization.provider,
                    "external_org_id": organization.external_org_id,
                    "created_at": organization.created_at.isoformat(),
                    "updated_at": organization.updated_at.isoformat(),
                },
            )
        except Exception as e:
            logger.error(f"Failed to publish organization SSE event: {e}", exc_info=True)

    # Queue background sync for repositories and PRs
    try:
        broker = get_faststream_broker()
        sync_message = GitHubSyncInstallationMessage(
            installation_id=installation_id,
            sender_github_id=sender_github_id,
        )
        await broker.publish(
            sync_message,
            stream="reviewate.events.github.sync_installation",
            maxlen=STREAM_MAXLEN,
        )
        logger.info(f"Queued repository sync for installation {installation_id}")
    except Exception as e:
        # Don't fail the webhook if queue publishing fails
        # User can manually sync repos later via API
        logger.error(
            f"Failed to queue repository sync for installation {installation_id}: {e}",
            exc_info=True,
        )

    # Queue background sync for organization members
    try:
        broker = get_faststream_broker()
        members_message = GitHubSyncMembersMessage(
            installation_id=installation_id,
            organization_id=str(organization.id),
            org_name=org_name,
        )
        await broker.publish(
            members_message,
            stream="reviewate.events.github.sync_members",
            maxlen=STREAM_MAXLEN,
        )
        logger.info(f"Queued member sync for organization {org_name}")
    except Exception as e:
        logger.error(
            f"Failed to queue member sync for organization {org_name}: {e}",
            exc_info=True,
        )

    return WebhookResponse(
        message=f"Organization {org_name} created successfully, syncing repositories and members in background",
        processed=True,
    )


async def handle_installation_deleted(
    event: GitHubAppInstallationEvent,
    db: Session,
) -> WebhookResponse:
    """Handle installation.deleted event - Delete organization.

    Args:
        event: GitHub App installation event
        db: Database session

    Returns:
        WebhookResponse confirmation
    """
    installation = event.installation
    installation_id = str(installation["id"])

    # Find and delete organization
    org = db_get_organization_by_installation_id(db, installation_id)

    if not org:
        return WebhookResponse(
            message="Organization not found (may have been deleted already)",
            processed=True,
        )

    org_name = org.name
    org_id = org.id

    # Get user_ids from organization memberships before deletion for SSE notification
    # Memberships link to provider_identities which may have user_id
    org_memberships = org.memberships if hasattr(org, "memberships") else []
    user_ids = []
    for membership in org_memberships:
        if membership.provider_identity and membership.provider_identity.user_id:
            user_ids.append(membership.provider_identity.user_id)

    db_delete_organization(db, installation_id)

    # Publish SSE event for organization deletion to all logged-in members
    for user_id in user_ids:
        try:
            await publish_organization_event(
                user_id=str(user_id),
                action="deleted",
                organization={
                    "id": str(org_id),
                    "name": org_name,
                },
            )
        except Exception as e:
            logger.error(f"Failed to publish organization deletion SSE event: {e}", exc_info=True)

    return WebhookResponse(
        message=f"Organization {org_name} deleted successfully",
        processed=True,
    )


async def handle_repositories_added(
    event: GitHubAppInstallationRepositoriesEvent,
    db: Session,
) -> WebhookResponse:
    """Handle installation_repositories.added event - Add repositories to installation.

    Args:
        event: GitHub App installation_repositories event
        db: Database session

    Returns:
        WebhookResponse confirmation
    """
    installation = event.installation
    installation_id = str(installation["id"])
    repositories_added = event.repositories_added or []

    # Find the organization
    org = db_get_organization_by_installation_id(db, installation_id)

    if not org:
        raise HTTPException(
            status_code=404,
            detail=f"Organization not found for installation {installation_id}",
        )

    # Find the provider identity who triggered this (if they exist in our system)
    sender = event.sender
    sender_github_id = str(sender["id"])
    sender_identity = db_get_identity_by_external_id(db, "github", sender_github_id)

    added_count = 0
    for repo_info in repositories_added:
        external_repo_id = str(repo_info["id"])

        # Check if repository already exists
        existing_repo = db_get_repository_by_external_id(db, external_repo_id)
        if existing_repo:
            continue  # Skip if already exists

        # Extract avatar URL from owner (repo's owner avatar)
        repo_avatar_url = repo_info.get("owner", {}).get("avatar_url")

        # Create repository
        repository = db_create_repository(
            db=db,
            organization_id=org.id,
            external_repo_id=external_repo_id,
            name=repo_info["name"],
            web_url=repo_info.get("html_url", ""),
            provider="github",
            provider_url="https://github.com",
            avatar_url=repo_avatar_url,
        )

        # Create repository membership for the user if they have a linked account
        if sender_identity and sender_identity.user_id:
            db_create_repository_membership(
                db=db,
                user_id=sender_identity.user_id,
                repository_id=repository.id,
                role="admin",
            )

        added_count += 1

        # Publish SSE event for repository creation
        try:
            await publish_repository_event(
                organization_id=str(org.id),
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

    return WebhookResponse(
        message=f"Added {added_count} repositories to organization {org.name}",
        processed=True,
    )


async def handle_repositories_removed(
    event: GitHubAppInstallationRepositoriesEvent,
    db: Session,
) -> WebhookResponse:
    """Handle installation_repositories.removed event - Remove repositories from installation.

    Args:
        event: GitHub App installation_repositories event
        db: Database session

    Returns:
        WebhookResponse confirmation
    """
    repositories_removed = event.repositories_removed or []

    removed_count = 0
    for repo_info in repositories_removed:
        external_repo_id = str(repo_info["id"])

        # Get repository info before deletion for SSE notification
        repo = db_get_repository_by_external_id(db, external_repo_id)
        if repo:
            repo_id = repo.id
            repo_name = repo.name
            org_id = repo.organization_id

            # Delete repository (cascade deletes memberships and executions)
            if db_delete_repository(db, external_repo_id):
                removed_count += 1

                # Publish SSE event for repository deletion
                try:
                    await publish_repository_event(
                        organization_id=str(org_id),
                        action="deleted",
                        repository={
                            "id": str(repo_id),
                            "name": repo_name,
                        },
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to publish repository deletion SSE event: {e}", exc_info=True
                    )

    return WebhookResponse(
        message=f"Removed {removed_count} repositories from installation",
        processed=True,
    )
