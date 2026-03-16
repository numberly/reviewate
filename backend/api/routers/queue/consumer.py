"""FastStream message handlers for queue processing.

Note: While this uses RedisRouter, the MESSAGE HANDLERS themselves (@router.subscriber)
are broker-agnostic. The same handler functions work with Redis, Kafka, RabbitMQ, etc.
You just need to create the appropriate broker in the plugin (RedisBroker, KafkaBroker, etc.)
and include this router.

FastStream handles the broker-specific details internally.
"""

import logging
from urllib.parse import urlparse
from uuid import UUID

from faststream.redis import RedisRouter, StreamSub
from redis.exceptions import LockError

from api.context import get_current_app
from api.database.execution import (
    db_get_latest_executions_for_pr,
    db_update_execution_container,
    db_update_execution_status,
)
from api.database.organization import db_get_organization_by_id
from api.database.pull_request import db_get_pull_request_by_id
from api.database.repository import db_get_repository_by_id
from api.plugins.container.platform_comments import upsert_bot_comment
from api.plugins.container.status_comment import MARKER, build_status_body
from api.plugins.container.utils import get_platform_token
from api.routers.queue.schemas import (
    ExecutionStatusMessage,
    ReviewJobMessage,
)
from api.sse.publishers import publish_pull_request_event

logger = logging.getLogger(__name__)

# Router for review queue handlers
# (handlers work with any FastStream broker - Redis, Kafka, RabbitMQ, etc.)
router = RedisRouter()


def _get_exposed_error_detail(execution) -> str | None:
    """Return error_detail if config allows exposing technical details."""
    if not execution.error_detail:
        return None
    try:
        app = get_current_app()
        if not app.options.expose_error_details:
            return None
    except Exception:
        pass
    return execution.error_detail


async def _publish_status_event(execution, workflow: str = "review") -> None:
    """Publish execution status event to dashboard SSE stream.

    Args:
        execution: Execution object with updated status
        workflow: Workflow type (review, summarize) — included in event for frontend filtering
    """
    await publish_pull_request_event(
        pull_request_id=str(execution.pull_request_id),
        action="execution_status_changed",
        organization_id=str(execution.organization_id),
        repository_id=str(execution.repository_id),
        latest_execution_id=str(execution.id),
        latest_execution_status=execution.status,
        updated_at=execution.updated_at.isoformat(),
        workflow=workflow,
        error_type=execution.error_type,
        error_detail=_get_exposed_error_detail(execution),
    )


@router.subscriber(
    stream=StreamSub("reviewate.review.jobs", group="reviewate", consumer="worker-1")
)
async def handle_review_job(message: ReviewJobMessage) -> None:
    """Handle code review job messages.

    This handler starts a container for the review job and returns immediately.
    The container watcher will monitor the container and update status via
    handle_execution_status when the container completes.

    Args:
        message: Review job message from queue
    """
    logger.info(
        "Processing %s job %s (%s/%s #%s)",
        message.workflow,
        message.job_id[:8],
        message.organization,
        message.repository,
        message.pull_request_number,
    )

    execution_id = UUID(message.job_id)
    app = get_current_app()
    backend = app.container.backend

    try:
        # Phase 1: Start container
        container_id = await backend.start_container(
            execution_id=message.job_id,
            job=message,
        )

        # Phase 2: DB write — update execution with container_id
        with app.database.session() as db:
            db_update_execution_container(db, execution_id, container_id)

        logger.debug(f"Started container {container_id[:12]} for execution {message.job_id}")

    except Exception as e:
        # Mark as failed if container couldn't start
        try:
            with app.database.session() as db:
                execution = db_update_execution_status(
                    db,
                    execution_id,
                    "failed",
                    error_type="container_error",
                    error_detail=str(e)[:2000],
                )

            logger.error(f"Updated execution {execution_id} to failed: {e}")

            if execution:
                await _publish_status_event(execution, workflow=message.workflow)
                await _update_status_comment_for_execution(execution)
        except Exception as db_error:
            logger.error(f"Failed to update execution status: {db_error}")

        logger.exception(
            "Failed to start container for review job",
            extra={
                "job_id": message.job_id,
                "error": str(e),
            },
        )

        # Re-raise to trigger FastStream's retry mechanism
        raise


@router.subscriber(
    stream=StreamSub("reviewate.execution.status", group="reviewate", consumer="worker-1")
)
async def handle_execution_status(message: ExecutionStatusMessage) -> None:
    """Handle execution status updates from container watcher.

    This handler receives status updates when containers start, complete,
    or fail, and updates the execution status in the database.

    Args:
        message: Execution status message from watcher
    """
    app = get_current_app()

    try:
        execution_id = UUID(message.execution_id)

        # Phase 1: DB write — update execution status
        with app.database.session() as db:
            execution = db_update_execution_status(
                db,
                execution_id,
                message.status,
                error_type=message.error_type,
                error_detail=message.error_message,
            )

        # Phase 2: Publish SSE event (Redis publish, no DB needed)
        if execution:
            logger.info(f"Execution {execution_id} -> {message.status}")

            await _publish_status_event(execution, workflow=execution.workflow)

            # Phase 3: Update sticky status comment
            await _update_status_comment_for_execution(execution)
        else:
            logger.warning(
                f"Execution {execution_id} not found for status update",
                extra={
                    "execution_id": str(execution_id),
                    "status": message.status,
                },
            )

    except Exception as e:
        logger.exception(
            "Failed to process execution status update",
            extra={
                "execution_id": message.execution_id,
                "status": message.status,
                "error": str(e),
            },
        )
        raise


async def _update_status_comment_for_execution(execution) -> None:
    """Update the sticky status comment on a PR after an execution status change.

    Loads related models from the execution's foreign keys, queries all
    latest executions for the PR, and upserts the status comment.

    Uses a Redis distributed lock per PR to prevent duplicate comments when
    multiple pods process executions for the same PR concurrently.
    Never raises — failures are logged.
    """
    try:
        app = get_current_app()
        redis = app.faststream.get_redis()
        lock_key = f"reviewate:status-comment:pr:{execution.pull_request_id}"
        lock = redis.lock(lock_key, timeout=30, blocking_timeout=10)

        try:
            async with lock:
                with app.database.session() as db:
                    pr = db_get_pull_request_by_id(db, execution.pull_request_id)
                    if not pr:
                        return
                    repository = db_get_repository_by_id(db, execution.repository_id)
                    if not repository:
                        return
                    organization = db_get_organization_by_id(db, execution.organization_id)
                    if not organization:
                        return

                    executions = db_get_latest_executions_for_pr(db, pr.id)
                    if not executions:
                        return

                    body = build_status_body(executions)

                    # Build minimal ReviewJobMessage to reuse get_platform_token
                    job = ReviewJobMessage(
                        job_id="status-comment",
                        organization_id=str(organization.id),
                        repository_id=str(repository.id),
                        pull_request_id=str(pr.id),
                        pull_request_number=pr.pr_number,
                        platform=organization.provider,
                        organization=organization.name,
                        repository=repository.name,
                        source_branch=pr.head_branch,
                        target_branch=pr.base_branch,
                        commit_sha=pr.head_sha,
                        workflow="review",
                        triggered_by="status_comment",
                    )

                token = await get_platform_token(job)
                if not token:
                    logger.warning("No platform token available for status comment")
                    return

                # Determine API URL
                if organization.provider == "github":
                    api_url = (
                        app.github.config.app.api_base_url
                        if app.github and app.github.config.app
                        else "https://api.github.com"
                    )
                else:
                    api_url = (
                        app.gitlab._get_base_url()
                        if app.gitlab
                        else f"{organization.provider_url}/api/v4"
                    )

                # Extract repo path from web_url
                parsed_url = urlparse(repository.web_url)
                repo_path = parsed_url.path.strip("/")

                await upsert_bot_comment(
                    platform=organization.provider,
                    api_url=api_url,
                    token=token,
                    repo=repo_path,
                    merge_id=pr.pr_number,
                    marker=MARKER,
                    body=body,
                )
        except LockError:
            logger.warning(
                "Could not acquire status comment lock for PR %s", execution.pull_request_id
            )
    except Exception:
        logger.exception("Failed to update status comment (non-blocking)")
