"""Shared webhook utilities for GitHub and GitLab handlers.

Common logic extracted from platform-specific handlers to reduce duplication.
"""

import logging
from datetime import UTC, datetime
from urllib.parse import urlparse

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.context import get_current_app
from api.database import (
    db_get_effective_linked_repos,
    db_get_membership_by_username,
)
from api.database.execution import (
    db_create_execution,
    db_has_active_execution,
)
from api.jobs.summarize_feedback import get_or_refresh_team_guidelines
from api.plugins.faststream import get_faststream_broker
from api.plugins.faststream.config import STREAM_MAXLEN
from api.routers.queue.schemas import LinkedRepoMessage, ReviewJobMessage

logger = logging.getLogger(__name__)


class WebhookResponse(BaseModel):
    """Generic webhook response."""

    message: str = Field(description="Response message")
    processed: bool = Field(description="Whether the webhook was processed", default=True)


# Label-to-workflow mapping shared by GitHub and GitLab handlers
LABEL_WORKFLOWS: dict[str, tuple[str, str]] = {
    "reviewate": ("automatic_review_trigger", "review"),
    "summarate": ("automatic_summary_trigger", "summarize"),
}


def get_effective_trigger(repository, organization, field: str) -> str:
    """Get effective trigger setting (repo override > org default).

    Args:
        repository: Repository model
        organization: Organization model
        field: Field name (e.g., "automatic_review_trigger" or "automatic_summary_trigger")

    Returns:
        Effective trigger value
    """
    trigger = getattr(repository, field)
    return trigger if trigger is not None else getattr(organization, field)


def is_feedback_loop_enabled() -> bool:
    """Check if feedback loop is enabled via app options."""
    app = get_current_app()
    return app.options.feedback_loop.enabled


def is_author_enabled(db: Session, organization_id, author_username: str) -> bool:
    """Check if the PR author has reviews enabled.

    Args:
        db: Database session
        organization_id: Organization ID
        author_username: Author's username

    Returns:
        True if reviews are enabled (default), False if explicitly disabled
    """
    membership = db_get_membership_by_username(db, organization_id, author_username)
    return not (membership and not membership.reviewate_enabled)


async def publish_pr_state_event(pr, created: bool) -> None:
    """Publish SSE event for PR state changes (create, close, reopen).

    Args:
        pr: PullRequest model
        created: Whether the PR was just created
    """
    try:
        broker = get_faststream_broker()
        pr_event_data = {
            "pull_request_id": str(pr.id),
            "organization_id": str(pr.organization_id),
            "repository_id": str(pr.repository_id),
            "action": "created" if created else "updated",
            "state": pr.state,
            "updated_at": pr.updated_at.isoformat(),
        }
        await broker.publish(pr_event_data, channel="reviewate.events.pull_requests")
    except Exception as e:
        logger.error(f"Failed to publish PR SSE event: {e}")


async def trigger_job(
    db: Session,
    organization,
    repository,
    pr,
    commit_sha: str,
    triggered_by: str,
    workflow: str = "review",
    pr_prefix: str = "#",
) -> WebhookResponse:
    """Trigger a review or summary job for a pull request / merge request.

    Args:
        db: Database session
        organization: Organization model
        repository: Repository model
        pr: PullRequest model
        commit_sha: Commit SHA to review
        triggered_by: Who/what triggered the job
        workflow: Job workflow type ("review" or "summarize")
        pr_prefix: PR number prefix ("#" for GitHub, "!" for GitLab)

    Returns:
        WebhookResponse confirmation
    """
    # Create execution record
    execution = db_create_execution(
        db=db,
        organization_id=repository.organization_id,
        repository_id=repository.id,
        pull_request_id=pr.id,
        pr_number=pr.pr_number,
        commit_sha=commit_sha,
        status="queued",
        workflow=workflow,
    )

    job_id = str(execution.id)

    # Extract repo path from web_url
    parsed_url = urlparse(repository.web_url)
    repo_path = parsed_url.path.strip("/")
    path_parts = repo_path.split("/", 1)
    repo_owner = path_parts[0] if path_parts else organization.name
    repo_name = path_parts[1] if len(path_parts) > 1 else repository.name

    # Get effective linked repos
    linked_repos_db = db_get_effective_linked_repos(db, repository.id)
    linked_repos_messages = [
        LinkedRepoMessage(
            provider=lr.linked_provider,
            provider_url=lr.linked_provider_url,
            repo_path=lr.linked_repo_path,
            branch=lr.linked_branch,
            display_name=lr.display_name,
            name=lr.display_name or lr.linked_repo_path.split("/")[-1],
        )
        for lr in linked_repos_db
    ]

    # Get team guidelines
    team_guidelines = await get_or_refresh_team_guidelines(
        organization_id=organization.id,
        repository_id=repository.id,
    )

    message = ReviewJobMessage(
        job_id=job_id,
        organization_id=str(organization.id),
        repository_id=str(repository.id),
        pull_request_id=str(pr.id),
        pull_request_number=pr.pr_number,
        platform=organization.provider,
        organization=repo_owner,
        repository=repo_name,
        source_branch=pr.head_branch,
        target_branch=pr.base_branch,
        commit_sha=commit_sha,
        workflow=workflow,
        triggered_by=triggered_by,
        triggered_at=datetime.now(UTC),
        context={
            "pr_url": pr.pr_url,
            "title": pr.title,
        },
        linked_repos=linked_repos_messages,
        team_guidelines=team_guidelines,
    )

    # Publish job message to review queue
    try:
        broker = get_faststream_broker()
        await broker.publish(
            message.model_dump(), stream="reviewate.review.jobs", maxlen=STREAM_MAXLEN
        )
        logger.info(f"Published {workflow} job {job_id} to queue (triggered by {triggered_by})")
    except Exception as e:
        logger.exception(f"Failed to publish {workflow} job to queue", extra={"job_id": job_id})
        return WebhookResponse(
            message=f"Failed to queue {workflow} job: {e!s}",
            processed=False,
        )

    # Publish PR update event (SSE — stays Pub/Sub)
    try:
        broker = get_faststream_broker()
        pr_event_data = {
            "pull_request_id": str(pr.id),
            "organization_id": str(pr.organization_id),
            "repository_id": str(pr.repository_id),
            "action": "execution_created",
            "latest_execution_id": str(execution.id),
            "latest_execution_status": "queued",
            "latest_execution_created_at": execution.created_at.isoformat(),
            "updated_at": pr.updated_at.isoformat(),
            "workflow": workflow,
        }
        await broker.publish(pr_event_data, channel="reviewate.events.pull_requests")
    except Exception as e:
        logger.error(f"Failed to publish PR update event: {e}")

    return WebhookResponse(
        message=f"{workflow.capitalize()} triggered for PR {pr_prefix}{pr.pr_number} by {triggered_by}",
        processed=True,
    )


async def check_and_trigger_workflows(
    db: Session,
    organization,
    repository,
    pr,
    commit_sha: str,
    trigger_type: str,
    pr_prefix: str = "#",
) -> None:
    """Check trigger settings and dispatch review/summary jobs if matched.

    Args:
        db: Database session
        organization: Organization model
        repository: Repository model
        pr: PullRequest model
        commit_sha: Commit SHA to review
        trigger_type: Trigger type ("creation" or "commit")
        pr_prefix: PR number prefix ("#" for GitHub, "!" for GitLab)
    """
    review_trigger = get_effective_trigger(repository, organization, "automatic_review_trigger")
    summary_trigger = get_effective_trigger(repository, organization, "automatic_summary_trigger")

    pr_label = f"PR {pr_prefix}{pr.pr_number} ({repository.name})"

    if review_trigger == trigger_type:
        logger.info(f"{pr_label}: triggering review (trigger={trigger_type})")
        await trigger_job(
            db=db,
            organization=organization,
            repository=repository,
            pr=pr,
            commit_sha=commit_sha,
            triggered_by=trigger_type,
            workflow="review",
            pr_prefix=pr_prefix,
        )
    else:
        logger.info(
            f"{pr_label}: review trigger is '{review_trigger}', not '{trigger_type}', skipping review"
        )

    if summary_trigger == trigger_type:
        logger.info(f"{pr_label}: triggering summarize (trigger={trigger_type})")
        await trigger_job(
            db=db,
            organization=organization,
            repository=repository,
            pr=pr,
            commit_sha=commit_sha,
            triggered_by=trigger_type,
            workflow="summarize",
            pr_prefix=pr_prefix,
        )
    else:
        logger.info(
            f"{pr_label}: summary trigger is '{summary_trigger}', not '{trigger_type}', skipping summary"
        )


async def check_label_triggers_at_creation(
    db: Session,
    organization,
    repository,
    pr,
    commit_sha: str,
    labels: list[dict],
    label_name_key: str = "name",
    pr_prefix: str = "#",
) -> None:
    """Check labels already present at PR/MR creation and trigger matching workflows.

    When a PR/MR is created with trigger labels already attached (e.g. "reviewate"),
    the normal "labeled" webhook event may not fire or may arrive after creation.
    This function inspects existing labels at creation time to fill that gap.

    Args:
        db: Database session
        organization: Organization model
        repository: Repository model
        pr: PullRequest model
        commit_sha: Commit SHA to review
        labels: List of label dicts from the webhook payload
        label_name_key: Key to extract label name ("name" for GitHub, "title" for GitLab)
        pr_prefix: PR number prefix ("#" for GitHub, "!" for GitLab)
    """
    pr_label = f"PR {pr_prefix}{pr.pr_number} ({repository.name})"

    for label_dict in labels:
        label_name = label_dict.get(label_name_key, "")
        if not label_name:
            continue

        for trigger_label, (trigger_field, workflow) in LABEL_WORKFLOWS.items():
            if label_name.lower() != trigger_label.lower():
                continue

            # Check if label trigger is enabled
            trigger_setting = get_effective_trigger(repository, organization, trigger_field)
            if trigger_setting != "label":
                logger.info(
                    f"{pr_label}: label trigger not enabled for {workflow} "
                    f"(current trigger={trigger_setting})"
                )
                break

            # Guard: skip if there's already an active execution
            if db_has_active_execution(db, pr.id, workflow):
                logger.info(f"{pr_label}: {workflow} already running, skipping")
                break

            logger.info(f"{pr_label}: triggering {workflow} via label:{label_name} (at creation)")
            await trigger_job(
                db=db,
                organization=organization,
                repository=repository,
                pr=pr,
                commit_sha=commit_sha,
                triggered_by=f"label:{label_name}",
                workflow=workflow,
                pr_prefix=pr_prefix,
            )
            break
