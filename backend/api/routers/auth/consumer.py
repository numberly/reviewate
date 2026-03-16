"""FastStream consumer for user membership sync operations.

This module processes background jobs for syncing user memberships
to organizations and repositories after OAuth login.
"""

import logging
from uuid import UUID

from faststream.redis import RedisRouter, StreamSub

from api.app import Application
from api.context import get_current_app
from api.database import (
    db_get_organization_by_external_id,
    db_get_organization_by_installation_id,
    db_get_repositories_by_organization,
    db_sync_organization_membership,
    db_sync_repository_membership,
)
from api.database.identity import db_get_identity_by_external_id
from api.routers.auth.schemas import SyncUserMembershipsMessage
from api.security import get_encryptor

logger = logging.getLogger(__name__)

# FastStream router for auth sync events
router = RedisRouter()


@router.subscriber(
    stream=StreamSub(
        "reviewate.events.auth.sync_memberships", group="reviewate", consumer="worker-1"
    )
)
async def sync_user_memberships(message: SyncUserMembershipsMessage) -> None:
    """Sync organization and repository memberships for a user after OAuth login.

    For GitHub:
    - Fetches orgs user belongs to via OAuth token
    - Finds orgs where our GitHub App is installed (have installation_id)
    - Creates org memberships and repo memberships

    For GitLab:
    - Fetches groups user belongs to via OAuth token
    - Finds groups that exist in our DB (by external_org_id)
    - Creates org memberships and repo memberships

    Args:
        message: Typed sync memberships message
    """
    user_id = message.user_id
    provider = message.provider

    logger.info(f"Starting membership sync for user {user_id} ({provider})")

    app = get_current_app()
    encryptor = get_encryptor()

    # Decrypt the access token
    try:
        access_token = encryptor.decrypt(message.access_token_encrypted)
    except Exception as e:
        logger.error(f"Failed to decrypt access token: {e}")
        return

    # Phase 1: DB read — get provider identity
    with app.database.session() as db:
        provider_identity = db_get_identity_by_external_id(
            db=db,
            provider=provider,
            external_id=message.external_user_id,
        )

        if not provider_identity:
            logger.error(f"Provider identity not found for {provider}:{message.external_user_id}")
            return

        provider_identity_id = provider_identity.id
        logger.debug(f"Found provider identity {provider_identity_id} for user {user_id}")

    # Phase 2: Delegate to provider-specific sync (manages own sessions)
    user_uuid = UUID(user_id)
    try:
        if provider == "github":
            await _sync_github_memberships(app, provider_identity_id, user_uuid, access_token)
        elif provider == "gitlab":
            await _sync_gitlab_memberships(
                app, provider_identity_id, user_uuid, access_token, message.external_user_id
            )
        else:
            logger.warning(f"Unknown provider: {provider}")
    except Exception as e:
        logger.error(f"Failed to sync memberships for user {user_id}: {e}", exc_info=True)


def _write_memberships_to_db(
    app: Application,
    provider_identity_id: UUID,
    user_id: UUID,
    org_roles: list[tuple[UUID, str]],
    provider_label: str,
) -> None:
    """Batch-write organization and repository memberships to the database."""
    orgs_synced = 0
    repos_synced = 0
    with app.database.session() as db:
        for org_id, role in org_roles:
            db_sync_organization_membership(
                db=db,
                provider_identity_id=provider_identity_id,
                organization_id=org_id,
                role=role,
            )
            orgs_synced += 1

            repos = db_get_repositories_by_organization(db, org_id)
            for repo in repos:
                db_sync_repository_membership(
                    db=db,
                    user_id=user_id,
                    repository_id=repo.id,
                    role=role,
                )
                repos_synced += 1

    logger.info(f"{provider_label} sync complete: {orgs_synced} orgs, {repos_synced} repos")


async def _sync_github_memberships(
    app: Application,
    provider_identity_id: UUID,
    user_id: UUID,
    access_token: str,
) -> None:
    """Sync GitHub organization memberships.

    Approach:
    1. Use /user/installations endpoint to get installations user has access to
    2. Each installation represents an org where the app is installed AND user is a member
    3. Look up org by installation_id in our DB
    4. If found, sync the membership

    This is efficient because:
    - Single API call to get all relevant installations
    - Works with private org memberships (doesn't require read:org scope)
    - Only returns orgs where both: app is installed AND user has access
    """
    github_plugin = app.github
    if not github_plugin:
        logger.warning("GitHub plugin not available")
        return

    # Phase 1: External API call — fetch installations
    try:
        installations = await github_plugin.fetch_user_installations(access_token)
    except Exception as e:
        logger.error(f"Failed to fetch user installations: {e}")
        return

    logger.debug(f"User has access to {len(installations)} GitHub App installations")

    if not installations:
        logger.debug("No accessible installations found, skipping GitHub sync")
        return

    # Phase 2: For each installation — DB lookup + API call → collect (org, role) pairs
    org_roles: list[tuple[UUID, str]] = []  # (org_id, role)
    for installation in installations:
        installation_id = str(installation["id"])
        account = installation.get("account", {})
        account_login = account.get("login", "unknown")

        # Short DB read to look up org
        with app.database.session() as db:
            org = db_get_organization_by_installation_id(db, installation_id)

        if not org:
            logger.debug(f"Installation {installation_id} ({account_login}) not in DB, skipping")
            continue

        # API call — no DB session held
        role = "member"
        try:
            role = await github_plugin.get_user_org_membership(access_token, account_login)
        except Exception as e:
            logger.warning(f"Failed to get role for org {account_login}: {e}")

        org_roles.append((org.id, role))

    # Phase 3: Batch DB writes
    _write_memberships_to_db(app, provider_identity_id, user_id, org_roles, "GitHub")


async def _sync_gitlab_memberships(
    app: Application,
    provider_identity_id: UUID,
    user_id: UUID,
    access_token: str,
    external_user_id: str,
) -> None:
    """Sync GitLab group memberships and user namespace."""
    gitlab_plugin = app.gitlab
    if not gitlab_plugin:
        logger.warning("GitLab plugin not available")
        return

    # Phase 1: External API calls — fetch groups and namespaces
    try:
        user_groups = await gitlab_plugin.fetch_user_groups(access_token)
    except Exception as e:
        logger.error(f"Failed to fetch GitLab groups: {e}")
        user_groups = []

    try:
        user_namespaces = await gitlab_plugin.fetch_user_namespaces(access_token)
    except Exception as e:
        logger.error(f"Failed to fetch GitLab namespaces: {e}")
        user_namespaces = []

    logger.debug(f"User has {len(user_namespaces)} namespaces, {len(user_groups)} groups")

    # Build list of namespace IDs to check (owned namespaces + groups)
    namespaces_to_check = []

    for ns in user_namespaces:
        is_personal = ns.get("kind") == "user"
        namespaces_to_check.append(
            {
                "id": ns["id"],
                "name": ns.get("name") or ns.get("path"),
                "is_personal": is_personal,
            }
        )

    for group_info in user_groups:
        namespaces_to_check.append(
            {
                "id": group_info["id"],
                "name": group_info["name"],
                "is_personal": False,
            }
        )

    # Phase 2: For each namespace — DB lookup + API call → collect (org_id, role) pairs
    org_roles: list[tuple[UUID, str]] = []
    for namespace_info in namespaces_to_check:
        external_org_id = str(namespace_info["id"])
        namespace_name = namespace_info["name"]
        is_personal = namespace_info["is_personal"]

        # Short DB read to look up org
        with app.database.session() as db:
            org = db_get_organization_by_external_id(db, external_org_id, provider="gitlab")

        if not org:
            logger.debug(f"GitLab org {namespace_name} (id={external_org_id}) not in DB, skipping")
            continue

        # Determine user's role
        if is_personal:
            role = "admin"
        else:
            # API call — no DB session held
            try:
                role = await gitlab_plugin.determine_user_role_in_group(
                    access_token=access_token,
                    group_id=external_org_id,
                    gitlab_user_id=external_user_id,
                )
            except Exception as e:
                logger.warning(f"Failed to determine role in group {namespace_name}: {e}")
                role = "member"

        org_roles.append((org.id, role))

    # Phase 3: Batch DB writes
    _write_memberships_to_db(app, provider_identity_id, user_id, org_roles, "GitLab")
