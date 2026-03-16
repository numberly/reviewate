"""SSE event publishers.

Helper functions to publish events to Redis channels for SSE streaming.
"""

import logging
from typing import Any

from api.plugins.faststream import get_faststream_broker
from api.routers.organizations.schemas import OrganizationEventMessage
from api.routers.pull_requests.schemas import PullRequestEventMessage
from api.routers.repositories.schemas import RepositoryEventMessage

logger = logging.getLogger(__name__)


async def publish_organization_event(
    user_id: str,
    action: str,
    organization: dict[str, Any],
) -> None:
    """Publish an organization update event.

    Args:
        user_id: User ID who should receive the update
        action: Action type (created, updated, deleted)
        organization: Organization data
    """
    try:
        broker = get_faststream_broker()
        message = OrganizationEventMessage(
            user_id=user_id,
            action=action,
            organization=organization,
            timestamp=organization.get("updated_at") or organization.get("created_at"),
        )
        await broker.publish(
            message,
            channel="reviewate.events.organizations",
        )
        logger.debug(f"Published organization {action} event for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to publish organization event: {e}", exc_info=True)


async def publish_repository_event(
    organization_id: str,
    action: str,
    repository: dict[str, Any],
) -> None:
    """Publish a repository update event.

    Args:
        organization_id: Organization ID that owns the repository
        action: Action type (created, updated, deleted)
        repository: Repository data
    """
    try:
        broker = get_faststream_broker()
        message = RepositoryEventMessage(
            organization_id=organization_id,
            action=action,
            repository=repository,
            timestamp=repository.get("updated_at") or repository.get("created_at"),
        )
        await broker.publish(
            message,
            channel="reviewate.events.repositories",
        )
        logger.debug(f"Published repository {action} event for org {organization_id}")
    except Exception as e:
        logger.error(f"Failed to publish repository event: {e}", exc_info=True)


async def publish_pull_request_event(
    pull_request_id: str,
    action: str,
    organization_id: str | None = None,
    repository_id: str | None = None,
    latest_execution_id: str | None = None,
    latest_execution_status: str | None = None,
    latest_execution_created_at: str | None = None,
    updated_at: str | None = None,
    error_type: str | None = None,
    error_detail: str | None = None,
    workflow: str | None = None,
) -> None:
    """Publish a pull request update event.

    Args:
        pull_request_id: Pull request ID
        action: Action type (execution_created, execution_status_changed)
        organization_id: Organization ID
        repository_id: Repository ID
        latest_execution_id: Latest execution ID
        latest_execution_status: Latest execution status
        latest_execution_created_at: Latest execution creation timestamp
        updated_at: Update timestamp
        error_type: Standardized error type (if execution failed)
        error_detail: Technical error detail (if execution failed)
        workflow: Workflow type (review, summarize)
    """
    try:
        broker = get_faststream_broker()
        message = PullRequestEventMessage(
            pull_request_id=pull_request_id,
            action=action,
            organization_id=organization_id,
            repository_id=repository_id,
            latest_execution_id=latest_execution_id,
            latest_execution_status=latest_execution_status,
            latest_execution_created_at=latest_execution_created_at,
            updated_at=updated_at,
            error_type=error_type,
            error_detail=error_detail,
            workflow=workflow,
        )
        await broker.publish(
            message,
            channel="reviewate.events.pull_requests",
        )
        logger.debug(f"Published pull request {action} event for PR {pull_request_id}")
    except Exception as e:
        logger.error(f"Failed to publish pull request event: {e}", exc_info=True)
