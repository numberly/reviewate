"""GitLab merge request webhook handlers."""

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
from .schemas import GitLabMergeRequestEvent

logger = logging.getLogger(__name__)


def _parse_gitlab_datetime(value: str) -> datetime:
    """Parse GitLab datetime strings.

    GitLab sends dates in varying formats:
    - '2026-01-12 09:56:49 UTC'
    - '2026-01-12T09:56:49Z'
    - '2026-01-12T09:56:49.000+00:00'
    """
    value = value.strip()
    if value.endswith(" UTC"):
        value = value[:-4] + "+00:00"
    elif value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


async def handle_merge_request_event(
    event: GitLabMergeRequestEvent,
    db: Session,
) -> WebhookResponse:
    """Handle GitLab merge request events and create/update PR records.

    Args:
        event: GitLab merge request event payload
        db: Database session

    Returns:
        WebhookResponse confirmation

    Raises:
        HTTPException: 404 if repository not found
    """
    # Extract MR details from object_attributes
    mr = event.object_attributes
    action = mr.get("action")
    mr_iid = mr.get("iid")
    project_name = event.project.get("path_with_namespace", "unknown")

    # Check for label changes in update action
    if action == "update" and event.changes:
        labels_change = event.changes.get("labels")
        if labels_change:
            # Detect newly added labels
            previous_labels = {lbl.get("title", "") for lbl in labels_change.get("previous", [])}
            current_labels = {lbl.get("title", "") for lbl in labels_change.get("current", [])}
            added_labels = current_labels - previous_labels

            if added_labels:
                logger.info(f"MR !{mr_iid} ({project_name}): labels added: {added_labels}")
                result = await _handle_label_trigger(event, db, added_labels)
                if result.processed:
                    return result
                # If label trigger didn't match, continue with normal processing

    # Process PR lifecycle events (open, update, reopen, close, merge)
    if action not in ["open", "update", "reopen", "close", "merge"]:
        logger.info(f"MR !{mr_iid} ({project_name}): ignoring action '{action}'")
        return WebhookResponse(
            message=f"Merge request action '{action}' ignored",
            processed=False,
        )

    logger.info(f"MR !{mr_iid} ({project_name}): handling action '{action}'")

    # Extract project and MR details
    project = event.project
    project_id = str(project.get("id"))
    mr_id = str(mr.get("id"))  # Internal GitLab MR ID

    # Find repository by external_repo_id (project_id)
    repository = db_get_repository_by_external_id(db, project_id)
    if not repository:
        logger.warning(
            f"MR !{mr_iid} ({project_name}): repository not found (project_id={project_id})"
        )
        raise HTTPException(
            status_code=404,
            detail=f"Repository not found for project ID {project_id}. Please add this repository to Reviewate first.",
        )

    # Parse the MR creation date from GitLab (ISO 8601 format)
    mr_created_at = None
    if mr.get("created_at"):
        mr_created_at = _parse_gitlab_datetime(mr["created_at"])

    # GitLab sends author as top-level event.user, not inside object_attributes.
    # On "open", event.user IS the author. On other actions, preserve existing author.
    mr_author = event.user.get("username", "unknown")

    # Create or update MR record
    pr, created = db_upsert_pull_request(
        db=db,
        organization_id=repository.organization_id,
        repository_id=repository.id,
        pr_number=mr_iid,
        external_pr_id=mr_id,
        title=mr.get("title", ""),
        author=mr_author,
        state=mr.get("state", "opened"),
        head_branch=mr.get("source_branch", ""),
        base_branch=mr.get("target_branch", ""),
        head_sha=mr.get("last_commit", {}).get("id", ""),
        pr_url=mr.get("url", ""),
        created_at=mr_created_at,
    )

    # Publish SSE event for PR create or meaningful updates (state/title change)
    # Skip generic "update" unless title changed — avoids noise from label/description/assignee edits
    should_publish = created or action in ["open", "close", "merge", "reopen"]
    if not should_publish and action == "update" and event.changes:
        should_publish = "title" in event.changes

    if should_publish:
        await publish_pr_state_event(pr, created)

    # Check creation/commit triggers for reviews and summaries
    if action in ["open", "update"]:
        organization = db_get_organization_by_id(db, repository.organization_id)
        if organization:
            if not is_author_enabled(db, organization.id, pr.author):
                logger.info(
                    f"MR !{mr_iid} ({project_name}): reviews disabled for author '{pr.author}'"
                )
            else:
                commit_sha = mr.get("last_commit", {}).get("id", pr.head_sha)
                trigger_type = "creation" if action == "open" else "commit"
                await check_and_trigger_workflows(
                    db=db,
                    organization=organization,
                    repository=repository,
                    pr=pr,
                    commit_sha=commit_sha,
                    trigger_type=trigger_type,
                    pr_prefix="!",
                )

                # Check labels already present at creation time
                if action == "open":
                    await check_label_triggers_at_creation(
                        db=db,
                        organization=organization,
                        repository=repository,
                        pr=pr,
                        commit_sha=commit_sha,
                        labels=event.labels or [],
                        label_name_key="title",
                        pr_prefix="!",
                    )

    action_str = "created" if created else "updated"
    return WebhookResponse(
        message=f"Merge request !{mr_iid} {action_str} successfully",
        processed=True,
    )


async def _handle_label_trigger(
    event: GitLabMergeRequestEvent,
    db: Session,
    added_labels: set[str],
) -> WebhookResponse:
    """Handle label trigger for GitLab merge requests.

    Triggers a review when the "reviewate" label is added and review trigger is "label".
    Triggers a summary when the "summarate" label is added and summary trigger is "label".

    GitLab sends all label changes in a single webhook (unlike GitHub which sends one
    event per label), so this function processes ALL matching labels.

    Args:
        event: GitLab merge request event
        db: Database session
        added_labels: Set of newly added label names

    Returns:
        WebhookResponse - processed=True if at least one job was triggered
    """
    # Collect all matching labels (case-insensitive)
    matched: list[tuple[str, str, str]] = []  # (label, trigger_field, workflow)
    for label in added_labels:
        for trigger_label, (field, wf) in LABEL_WORKFLOWS.items():
            if label.lower() == trigger_label.lower():
                matched.append((label, field, wf))
                break

    if not matched:
        return WebhookResponse(
            message="Trigger label not in added labels",
            processed=False,
        )

    mr = event.object_attributes
    project = event.project
    project_id = str(project.get("id"))
    mr_iid = mr.get("iid")
    project_name = project.get("path_with_namespace", "unknown")

    # Find repository
    repository = db_get_repository_by_external_id(db, project_id)
    if not repository:
        logger.warning(
            f"MR !{mr_iid} ({project_name}): repository not found (project_id={project_id})"
        )
        return WebhookResponse(
            message=f"Repository not found for project ID {project_id}",
            processed=False,
        )

    # Get organization
    organization = db_get_organization_by_id(db, repository.organization_id)
    if not organization:
        logger.warning(f"MR !{mr_iid} ({project_name}): organization not found")
        return WebhookResponse(
            message="Organization not found",
            processed=False,
        )

    mr_id = str(mr.get("id"))

    # Get or create MR in our database
    pr = db_get_pull_request_by_pr_number(db, repository.id, mr_iid)
    if not pr:
        logger.info(f"MR !{mr_iid} ({project_name}): MR not in database, creating")
        mr_created_at = None
        if mr.get("created_at"):
            mr_created_at = _parse_gitlab_datetime(mr["created_at"])

        pr, _ = db_upsert_pull_request(
            db=db,
            organization_id=repository.organization_id,
            repository_id=repository.id,
            pr_number=mr_iid,
            external_pr_id=mr_id,
            title=mr.get("title", ""),
            author=event.user.get("username", "unknown"),
            state=mr.get("state", "opened"),
            head_branch=mr.get("source_branch", ""),
            base_branch=mr.get("target_branch", ""),
            head_sha=mr.get("last_commit", {}).get("id", ""),
            pr_url=mr.get("url", ""),
            created_at=mr_created_at,
        )

    # Check if author has reviews disabled
    if not is_author_enabled(db, organization.id, pr.author):
        logger.info(f"MR !{mr_iid} ({project_name}): reviews disabled for author '{pr.author}'")
        return WebhookResponse(
            message=f"Reviews disabled for author '{pr.author}'",
            processed=False,
        )

    # Get commit SHA
    commit_sha = mr.get("last_commit", {}).get("id", pr.head_sha)

    # Process each matched label independently
    last_result = WebhookResponse(message="No label triggers matched", processed=False)
    any_triggered = False

    for label_name, trigger_field, workflow in matched:
        # Check if label trigger is enabled (repo setting overrides org)
        trigger_setting = get_effective_trigger(repository, organization, trigger_field)
        if trigger_setting != "label":
            logger.info(
                f"MR !{mr_iid} ({project_name}): label trigger not enabled for {workflow} "
                f"(current trigger={trigger_setting})"
            )
            continue

        # Guard: skip if there's already an active execution for this PR+workflow
        if db_has_active_execution(db, pr.id, workflow):
            logger.info(f"MR !{mr_iid} ({project_name}): {workflow} already running, skipping")
            continue

        logger.info(f"MR !{mr_iid} ({project_name}): triggering {workflow} via label:{label_name}")

        # Trigger the job
        last_result = await trigger_job(
            db=db,
            organization=organization,
            repository=repository,
            pr=pr,
            commit_sha=commit_sha,
            triggered_by=f"label:{label_name}",
            workflow=workflow,
            pr_prefix="!",
        )
        if last_result.processed:
            any_triggered = True

    if any_triggered:
        last_result.processed = True
    return last_result
