"""GitHub pull request webhook handlers."""

import logging
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from api.database import (
    db_get_organization_by_id,
    db_get_repository_by_external_id,
    db_upsert_pull_request,
)
from api.database.execution import db_has_active_execution
from api.database.pull_request import db_get_pull_request_by_pr_number

from ..utils import (
    LABEL_WORKFLOWS,
    WebhookResponse,
    check_and_trigger_workflows,
    check_label_triggers_at_creation,
    get_effective_trigger,
    is_author_enabled,
    publish_pr_state_event,
    trigger_job,
)
from .schemas import GitHubPullRequestEvent

logger = logging.getLogger(__name__)


async def handle_pull_request_event(
    event: GitHubPullRequestEvent,
    db: Session,
) -> WebhookResponse:
    """Handle GitHub pull request events and create/update PR records.

    Args:
        event: GitHub pull request event payload
        db: Database session

    Returns:
        WebhookResponse confirmation

    Raises:
        HTTPException: 404 if repository not found
    """
    # Handle labeled action separately for review trigger
    action = event.action
    pr_number = event.number
    repo_name = event.repository.get("full_name", "unknown")

    if action == "labeled":
        return await handle_pull_request_labeled(event, db)

    # Process PR lifecycle events (opened, synchronize, reopened, closed)
    if action not in ["opened", "synchronize", "reopened", "closed"]:
        logger.info(f"PR #{pr_number} ({repo_name}): ignoring action '{action}'")
        return WebhookResponse(
            message=f"Pull request action '{action}' ignored",
            processed=False,
        )

    logger.info(f"PR #{pr_number} ({repo_name}): handling action '{action}'")

    # Extract repository and PR details
    repository_data = event.repository
    pr_data = event.pull_request

    repo_id = str(repository_data.get("id"))
    pr_id = str(pr_data.get("id"))

    # Find repository by external_repo_id
    repository = db_get_repository_by_external_id(db, repo_id)
    if not repository:
        logger.warning(
            f"PR #{pr_number} ({repo_name}): repository not found (external_id={repo_id})"
        )
        raise HTTPException(
            status_code=404,
            detail=f"Repository not found for repo ID {repo_id}. Please add this repository to Reviewate first.",
        )

    # Parse the PR creation date from GitHub (ISO 8601 format)
    pr_created_at = None
    if pr_data.get("created_at"):
        pr_created_at = datetime.fromisoformat(pr_data["created_at"].replace("Z", "+00:00"))

    # Create or update PR record
    pr, created = db_upsert_pull_request(
        db=db,
        organization_id=repository.organization_id,
        repository_id=repository.id,
        pr_number=pr_number,
        external_pr_id=pr_id,
        title=pr_data.get("title", ""),
        author=pr_data.get("user", {}).get("login", "unknown"),
        state=pr_data.get("state", "open"),
        head_branch=pr_data.get("head", {}).get("ref", ""),
        base_branch=pr_data.get("base", {}).get("ref", ""),
        head_sha=pr_data.get("head", {}).get("sha", ""),
        pr_url=pr_data.get("html_url", ""),
        created_at=pr_created_at,
    )

    # Publish SSE event for PR create or state change (close, reopen)
    # Skip synchronize (new commits) — if auto-review triggers, execution_created notifies instead
    if action != "synchronize":
        await publish_pr_state_event(pr, created)

    # Check creation/commit triggers for reviews and summaries
    if action in ["opened", "synchronize"]:
        organization = db_get_organization_by_id(db, repository.organization_id)
        if organization:
            author_username = pr_data.get("user", {}).get("login", pr.author)
            if not is_author_enabled(db, organization.id, author_username):
                logger.info(
                    f"PR #{pr_number} ({repo_name}): reviews disabled for author '{author_username}'"
                )
            else:
                commit_sha = pr_data.get("head", {}).get("sha", pr.head_sha)
                trigger_type = "creation" if action == "opened" else "commit"
                await check_and_trigger_workflows(
                    db=db,
                    organization=organization,
                    repository=repository,
                    pr=pr,
                    commit_sha=commit_sha,
                    trigger_type=trigger_type,
                )

                # Check labels already present at creation time
                if action == "opened":
                    await check_label_triggers_at_creation(
                        db=db,
                        organization=organization,
                        repository=repository,
                        pr=pr,
                        commit_sha=commit_sha,
                        labels=pr_data.get("labels", []),
                    )

    action_str = "created" if created else "updated"
    return WebhookResponse(
        message=f"Pull request #{pr_number} {action_str} successfully",
        processed=True,
    )


async def handle_pull_request_labeled(
    event: GitHubPullRequestEvent,
    db: Session,
) -> WebhookResponse:
    """Handle GitHub pull request labeled events and trigger jobs if label matches.

    Triggers a review when the "reviewate" label is added and review trigger is "label".
    Triggers a summary when the "summarate" label is added and summary trigger is "label".

    Args:
        event: GitHub pull request event payload with action="labeled"
        db: Database session

    Returns:
        WebhookResponse confirmation
    """
    pr_data = event.pull_request
    repository_data = event.repository
    pr_number = event.number
    repo_name = repository_data.get("full_name", "unknown")

    # Extract the label that was just added (top-level field in GitHub webhook, not inside pull_request)
    label = event.label or {}
    label_name = label.get("name", "")

    logger.info(f"PR #{pr_number} ({repo_name}): label '{label_name}' added")

    if not label_name:
        return WebhookResponse(
            message="No label name found in event",
            processed=False,
        )

    # Check if the added label matches any trigger label (case-insensitive)
    matched = None
    for trigger_label, (trigger_field, workflow) in LABEL_WORKFLOWS.items():
        if label_name.lower() == trigger_label.lower():
            matched = (trigger_field, workflow)
            break

    if not matched:
        logger.info(
            f"PR #{pr_number} ({repo_name}): label '{label_name}' is not a trigger label, skipping"
        )
        return WebhookResponse(
            message=f"Label '{label_name}' is not a trigger label",
            processed=False,
        )

    trigger_field, workflow = matched
    repo_id = str(repository_data.get("id"))

    # Find repository
    repository = db_get_repository_by_external_id(db, repo_id)
    if not repository:
        logger.warning(
            f"PR #{pr_number} ({repo_name}): repository not found (external_id={repo_id})"
        )
        return WebhookResponse(
            message=f"Repository not found for repo ID {repo_id}",
            processed=False,
        )

    # Get organization
    organization = db_get_organization_by_id(db, repository.organization_id)
    if not organization:
        logger.warning(f"PR #{pr_number} ({repo_name}): organization not found")
        return WebhookResponse(
            message="Organization not found",
            processed=False,
        )

    # Check if label trigger is enabled (repo setting overrides org)
    trigger_setting = get_effective_trigger(repository, organization, trigger_field)

    if trigger_setting != "label":
        logger.info(
            f"PR #{pr_number} ({repo_name}): label trigger not enabled for {workflow} "
            f"(current trigger={trigger_setting})"
        )
        return WebhookResponse(
            message=f"Label trigger not enabled for {workflow} in this repository",
            processed=False,
        )

    # Check if PR exists in our database
    pr = db_get_pull_request_by_pr_number(db, repository.id, pr_number)
    if not pr:
        # PR not in our database, might need to create it first
        logger.info(f"PR #{pr_number} ({repo_name}): PR not in database, creating")
        pr_id = str(pr_data.get("id"))
        pr_created_at = None
        if pr_data.get("created_at"):
            pr_created_at = datetime.fromisoformat(pr_data["created_at"].replace("Z", "+00:00"))

        pr, _ = db_upsert_pull_request(
            db=db,
            organization_id=repository.organization_id,
            repository_id=repository.id,
            pr_number=pr_number,
            external_pr_id=pr_id,
            title=pr_data.get("title", ""),
            author=pr_data.get("user", {}).get("login", "unknown"),
            state=pr_data.get("state", "open"),
            head_branch=pr_data.get("head", {}).get("ref", ""),
            base_branch=pr_data.get("base", {}).get("ref", ""),
            head_sha=pr_data.get("head", {}).get("sha", ""),
            pr_url=pr_data.get("html_url", ""),
            created_at=pr_created_at,
        )

    # Check if author has reviews disabled
    author_username = pr_data.get("user", {}).get("login", pr.author)
    if not is_author_enabled(db, organization.id, author_username):
        logger.info(
            f"PR #{pr_number} ({repo_name}): reviews disabled for author '{author_username}'"
        )
        return WebhookResponse(
            message=f"Reviews disabled for author '{author_username}'",
            processed=False,
        )

    # Get the commit SHA
    commit_sha = pr_data.get("head", {}).get("sha", pr.head_sha)

    # Guard: skip if there's already an active execution for this PR+workflow
    if db_has_active_execution(db, pr.id, workflow):
        logger.info(f"PR #{pr_number} ({repo_name}): {workflow} already running, skipping")
        return WebhookResponse(
            message=f"Skipped: {workflow} already running for PR #{pr.pr_number}",
            processed=False,
        )

    logger.info(f"PR #{pr_number} ({repo_name}): triggering {workflow} via label:{label_name}")

    # Trigger the job
    return await trigger_job(
        db=db,
        organization=organization,
        repository=repository,
        pr=pr,
        commit_sha=commit_sha,
        triggered_by=f"label:{label_name}",
        workflow=workflow,
    )
