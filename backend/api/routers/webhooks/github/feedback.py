"""GitHub feedback webhook handlers."""

import logging

from sqlalchemy.orm import Session

from api.database import (
    db_create_feedback,
    db_get_repository_by_external_id,
)

from ..utils import (
    WebhookResponse,
    is_feedback_loop_enabled,
)
from .schemas import (
    GitHubIssueCommentEvent,
    GitHubPullRequestReviewCommentEvent,
    GitHubPullRequestReviewEvent,
)

logger = logging.getLogger(__name__)


def _is_reviewate_comment(comment: dict) -> bool:
    """Check if a comment was made by Reviewate bot."""
    user = comment.get("user", {})
    login = user.get("login", "")
    # Check for common bot naming patterns
    return "reviewate" in login.lower() or user.get("type") == "Bot"


async def handle_issue_comment_event(
    event: GitHubIssueCommentEvent,
    db: Session,
) -> WebhookResponse:
    """Handle issue_comment events for feedback capture.

    Captures reply comments to Reviewate review comments.
    Stores raw feedback directly in database (no LLM processing).

    Args:
        event: GitHub issue comment event payload
        db: Database session

    Returns:
        WebhookResponse confirmation
    """
    # Check if feedback loop is enabled
    if not is_feedback_loop_enabled():
        return WebhookResponse(
            message="Feedback loop disabled, ignoring issue_comment event",
            processed=False,
        )

    # Only process created comments
    if event.action != "created":
        return WebhookResponse(
            message=f"Issue comment action '{event.action}' ignored",
            processed=False,
        )

    # Check if this is a PR (issues and PRs share the issue_comment event)
    issue = event.issue
    if "pull_request" not in issue:
        return WebhookResponse(
            message="Not a PR comment, ignoring",
            processed=False,
        )

    comment = event.comment
    repository_data = event.repository

    repo_id = str(repository_data.get("id"))
    repository = db_get_repository_by_external_id(db, repo_id)
    if not repository:
        return WebhookResponse(
            message="Repository not found, ignoring feedback",
            processed=False,
        )

    # Store raw feedback directly (simplified approach)
    try:
        user_reply = comment.get("body", "")
        if user_reply:
            db_create_feedback(
                db=db,
                organization_id=repository.organization_id,
                repository_id=repository.id,
                feedback_type="reply",
                review_comment="",  # No context for issue comments
                user_response=user_reply,
                platform="github",
            )
            logger.info(f"Stored reply feedback for repo {repository.name}")
    except Exception as e:
        logger.error(f"Failed to store feedback: {e}", exc_info=True)

    return WebhookResponse(
        message="Issue comment feedback captured",
        processed=True,
    )


async def handle_pull_request_review_comment_event(
    event: GitHubPullRequestReviewCommentEvent,
    db: Session,
) -> WebhookResponse:
    """Handle pull_request_review_comment events for feedback capture.

    Captures reactions (thumbs-down) on Reviewate review comments.
    Stores raw feedback directly in database (no LLM processing).

    Args:
        event: GitHub PR review comment event payload
        db: Database session

    Returns:
        WebhookResponse confirmation
    """
    # Check if feedback loop is enabled
    if not is_feedback_loop_enabled():
        return WebhookResponse(
            message="Feedback loop disabled, ignoring review_comment event",
            processed=False,
        )

    comment = event.comment
    repository_data = event.repository

    # Check if this is a Reviewate comment
    if not _is_reviewate_comment(comment):
        return WebhookResponse(
            message="Not a Reviewate comment, ignoring",
            processed=False,
        )

    # Check for thumbs-down reaction
    reactions = comment.get("reactions", {})
    if reactions.get("-1", 0) == 0:
        return WebhookResponse(
            message="No thumbs-down reaction, ignoring",
            processed=False,
        )

    repo_id = str(repository_data.get("id"))
    repository = db_get_repository_by_external_id(db, repo_id)
    if not repository:
        return WebhookResponse(
            message="Repository not found, ignoring feedback",
            processed=False,
        )

    # Store raw feedback directly (simplified approach)
    try:
        db_create_feedback(
            db=db,
            organization_id=repository.organization_id,
            repository_id=repository.id,
            feedback_type="thumbs_down",
            review_comment=comment.get("body", ""),
            file_path=comment.get("path"),
            platform="github",
        )
        logger.info(f"Stored thumbs-down feedback for review comment on repo {repository.name}")
    except Exception as e:
        logger.error(f"Failed to store feedback: {e}", exc_info=True)

    return WebhookResponse(
        message="Review comment feedback captured",
        processed=True,
    )


async def handle_pull_request_review_event(
    event: GitHubPullRequestReviewEvent,
    db: Session,
) -> WebhookResponse:
    """Handle pull_request_review events for feedback capture.

    Captures dismissed Reviewate reviews.
    Stores raw feedback directly in database (no LLM processing).

    Args:
        event: GitHub PR review event payload
        db: Database session

    Returns:
        WebhookResponse confirmation
    """
    # Check if feedback loop is enabled
    if not is_feedback_loop_enabled():
        return WebhookResponse(
            message="Feedback loop disabled, ignoring review event",
            processed=False,
        )

    # Only process dismissed reviews
    if event.action != "dismissed":
        return WebhookResponse(
            message=f"Review action '{event.action}' ignored",
            processed=False,
        )

    review = event.review
    repository_data = event.repository

    # Check if this is a Reviewate review
    if not _is_reviewate_comment(review):
        return WebhookResponse(
            message="Not a Reviewate review, ignoring",
            processed=False,
        )

    repo_id = str(repository_data.get("id"))
    repository = db_get_repository_by_external_id(db, repo_id)
    if not repository:
        return WebhookResponse(
            message="Repository not found, ignoring feedback",
            processed=False,
        )

    # Store raw feedback directly (simplified approach)
    try:
        db_create_feedback(
            db=db,
            organization_id=repository.organization_id,
            repository_id=repository.id,
            feedback_type="dismissed",
            review_comment=review.get("body", ""),
            platform="github",
        )
        logger.info(f"Stored dismissed review feedback on repo {repository.name}")
    except Exception as e:
        logger.error(f"Failed to store feedback: {e}", exc_info=True)

    return WebhookResponse(
        message="Dismissed review feedback captured",
        processed=True,
    )
