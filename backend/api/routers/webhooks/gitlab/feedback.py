"""GitLab feedback webhook handlers."""

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
from .schemas import GitLabNoteEvent

logger = logging.getLogger(__name__)


def _is_reviewate_note(note: dict, user: dict) -> bool:
    """Check if a note was made by Reviewate bot."""
    username = user.get("username", "")
    # Check for common bot naming patterns
    return "reviewate" in username.lower()


async def handle_note_event(
    event: GitLabNoteEvent,
    db: Session,
) -> WebhookResponse:
    """Handle GitLab note (comment) events for feedback capture.

    Captures reply comments to Reviewate review notes.
    Stores raw feedback directly in database (no LLM processing).

    Args:
        event: GitLab note event payload
        db: Database session

    Returns:
        WebhookResponse confirmation
    """
    # Check if feedback loop is enabled
    if not is_feedback_loop_enabled():
        return WebhookResponse(
            message="Feedback loop disabled, ignoring note event",
            processed=False,
        )

    note = event.object_attributes
    project = event.project

    # Only process notes on merge requests
    if not event.merge_request:
        return WebhookResponse(
            message="Not an MR note, ignoring",
            processed=False,
        )

    project_id = str(project.get("id"))

    # Find repository
    repository = db_get_repository_by_external_id(db, project_id)
    if not repository:
        return WebhookResponse(
            message="Repository not found, ignoring feedback",
            processed=False,
        )

    # Extract note content
    note_body = note.get("note", "")
    file_path = note.get("position", {}).get("new_path") if note.get("position") else None

    # Store raw feedback directly (simplified approach)
    try:
        if note_body:
            db_create_feedback(
                db=db,
                organization_id=repository.organization_id,
                repository_id=repository.id,
                feedback_type="reply",
                review_comment="",  # No context for note events
                user_response=note_body,
                file_path=file_path,
                platform="gitlab",
            )
            logger.info(f"Stored reply feedback for note on repo {repository.name}")
    except Exception as e:
        logger.error(f"Failed to store feedback: {e}", exc_info=True)

    return WebhookResponse(
        message="Note feedback captured",
        processed=True,
    )
