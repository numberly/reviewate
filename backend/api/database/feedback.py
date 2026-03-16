"""Database operations for Feedback model."""

from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.orm import Session

from api.models.feedback import Feedback


def db_create_feedback(
    db: Session,
    organization_id: UUID,
    feedback_type: str,
    review_comment: str,
    platform: str,
    repository_id: UUID | None = None,
    user_response: str | None = None,
    file_path: str | None = None,
) -> Feedback:
    """Create a new feedback record.

    Args:
        db: Database session
        organization_id: Organization ID
        feedback_type: Type of feedback (thumbs_down, reply, dismissed, etc.)
        review_comment: The AI comment that received feedback
        platform: Platform (github or gitlab)
        repository_id: Optional repository ID for repo-specific feedback
        user_response: User's reply text if any
        file_path: File path where comment was made

    Returns:
        Created Feedback record
    """
    feedback = Feedback(
        organization_id=organization_id,
        repository_id=repository_id,
        feedback_type=feedback_type,
        review_comment=review_comment,
        user_response=user_response,
        file_path=file_path,
        platform=platform,
        processed=False,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


def db_get_feedback_by_id(
    db: Session,
    feedback_id: UUID,
) -> Feedback | None:
    """Get feedback by ID.

    Args:
        db: Database session
        feedback_id: Feedback ID

    Returns:
        Feedback if found, None otherwise
    """
    return db.query(Feedback).filter(Feedback.id == feedback_id).first()


def db_get_unprocessed_feedback(
    db: Session,
    organization_id: UUID,
    repository_id: UUID | None = None,
    limit: int = 500,
) -> list[Feedback]:
    """Get unprocessed feedback for an organization.

    Args:
        db: Database session
        organization_id: Organization ID
        repository_id: Optional repository ID to filter by (None = org-wide only)
        limit: Maximum number of records to return

    Returns:
        List of unprocessed Feedback records
    """
    query = db.query(Feedback).filter(
        Feedback.organization_id == organization_id,
        Feedback.processed.is_(False),
    )

    if repository_id is not None:
        # Get repo-specific feedback
        query = query.filter(Feedback.repository_id == repository_id)
    else:
        # Get org-wide feedback (no repo specified)
        query = query.filter(Feedback.repository_id.is_(None))

    return query.order_by(Feedback.created_at.asc()).limit(limit).all()


def db_get_all_unprocessed_feedback_for_org(
    db: Session,
    organization_id: UUID,
    limit: int = 500,
) -> list[Feedback]:
    """Get all unprocessed feedback for an organization (both org-wide and repo-specific).

    Args:
        db: Database session
        organization_id: Organization ID
        limit: Maximum number of records to return

    Returns:
        List of unprocessed Feedback records
    """
    return (
        db.query(Feedback)
        .filter(
            Feedback.organization_id == organization_id,
            Feedback.processed.is_(False),
        )
        .order_by(Feedback.created_at.asc())
        .limit(limit)
        .all()
    )


def db_get_feedback_by_organization(
    db: Session,
    organization_id: UUID,
    repository_id: UUID | None = None,
    include_processed: bool = True,
    limit: int = 100,
    offset: int = 0,
) -> list[Feedback]:
    """Get feedback records for an organization.

    Args:
        db: Database session
        organization_id: Organization ID
        repository_id: Optional repository ID to filter by
        include_processed: Include processed feedback
        limit: Maximum number of records
        offset: Offset for pagination

    Returns:
        List of Feedback records
    """
    query = db.query(Feedback).filter(
        Feedback.organization_id == organization_id,
    )

    if repository_id is not None:
        query = query.filter(Feedback.repository_id == repository_id)

    if not include_processed:
        query = query.filter(Feedback.processed.is_(False))

    return query.order_by(Feedback.created_at.desc()).offset(offset).limit(limit).all()


def db_mark_feedback_processed(
    db: Session,
    feedback_ids: list[UUID],
) -> int:
    """Mark multiple feedback records as processed.

    Args:
        db: Database session
        feedback_ids: List of feedback IDs to mark as processed

    Returns:
        Number of records updated
    """
    if not feedback_ids:
        return 0

    result = (
        db.query(Feedback)
        .filter(Feedback.id.in_(feedback_ids))
        .update({Feedback.processed: True}, synchronize_session=False)
    )
    db.commit()
    return result


def db_delete_feedback(
    db: Session,
    feedback_id: UUID,
) -> bool:
    """Delete a feedback record.

    Args:
        db: Database session
        feedback_id: Feedback ID

    Returns:
        True if deleted, False if not found
    """
    feedback = db_get_feedback_by_id(db, feedback_id)
    if feedback:
        db.delete(feedback)
        db.commit()
        return True
    return False


def db_delete_feedback_by_organization(
    db: Session,
    organization_id: UUID,
    repository_id: UUID | None = None,
    processed_only: bool = False,
) -> int:
    """Delete feedback records for an organization.

    Args:
        db: Database session
        organization_id: Organization ID
        repository_id: Optional repository ID to filter by
        processed_only: Only delete processed feedback

    Returns:
        Number of records deleted
    """
    filters = [Feedback.organization_id == organization_id]

    if repository_id is not None:
        filters.append(Feedback.repository_id == repository_id)

    if processed_only:
        filters.append(Feedback.processed.is_(True))

    result = db.query(Feedback).filter(and_(*filters)).delete(synchronize_session=False)
    db.commit()
    return result
