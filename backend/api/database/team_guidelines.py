"""Database operations for TeamGuidelines model."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from api.models.team_guidelines import TeamGuidelines


def db_create_team_guidelines(
    db: Session,
    organization_id: UUID,
    guidelines_text: str,
    feedback_count: int = 0,
    repository_id: UUID | None = None,
) -> TeamGuidelines:
    """Create new team guidelines.

    Args:
        db: Database session
        organization_id: Organization ID
        guidelines_text: Natural language guidelines from LLM
        feedback_count: Number of feedbacks that contributed
        repository_id: Optional repository ID for repo-specific guidelines

    Returns:
        Created TeamGuidelines record
    """
    guidelines = TeamGuidelines(
        organization_id=organization_id,
        repository_id=repository_id,
        guidelines_text=guidelines_text,
        feedback_count=feedback_count,
    )
    db.add(guidelines)
    db.commit()
    db.refresh(guidelines)
    return guidelines


def db_get_team_guidelines_by_id(
    db: Session,
    guidelines_id: UUID,
) -> TeamGuidelines | None:
    """Get team guidelines by ID.

    Args:
        db: Database session
        guidelines_id: Guidelines ID

    Returns:
        TeamGuidelines if found, None otherwise
    """
    return db.query(TeamGuidelines).filter(TeamGuidelines.id == guidelines_id).first()


def db_get_team_guidelines(
    db: Session,
    organization_id: UUID,
    repository_id: UUID | None = None,
) -> TeamGuidelines | None:
    """Get team guidelines for an organization/repository scope.

    Args:
        db: Database session
        organization_id: Organization ID
        repository_id: Optional repository ID (None = org-wide guidelines)

    Returns:
        TeamGuidelines if found, None otherwise
    """
    query = db.query(TeamGuidelines).filter(
        TeamGuidelines.organization_id == organization_id,
    )

    if repository_id is not None:
        query = query.filter(TeamGuidelines.repository_id == repository_id)
    else:
        query = query.filter(TeamGuidelines.repository_id.is_(None))

    return query.first()


def db_get_effective_team_guidelines(
    db: Session,
    organization_id: UUID,
    repository_id: UUID | None = None,
) -> TeamGuidelines | None:
    """Get the most specific applicable team guidelines.

    If repository_id is provided, tries repo-specific first, then falls back to org-wide.
    If repository_id is None, returns org-wide guidelines.

    Args:
        db: Database session
        organization_id: Organization ID
        repository_id: Optional repository ID

    Returns:
        Most specific TeamGuidelines if found, None otherwise
    """
    if repository_id is not None:
        # Try repo-specific first
        repo_guidelines = db_get_team_guidelines(db, organization_id, repository_id)
        if repo_guidelines:
            return repo_guidelines

    # Fall back to org-wide
    return db_get_team_guidelines(db, organization_id, None)


def db_get_all_team_guidelines_for_org(
    db: Session,
    organization_id: UUID,
) -> list[TeamGuidelines]:
    """Get all team guidelines for an organization (org-wide and repo-specific).

    Args:
        db: Database session
        organization_id: Organization ID

    Returns:
        List of TeamGuidelines records
    """
    return (
        db.query(TeamGuidelines)
        .filter(TeamGuidelines.organization_id == organization_id)
        .order_by(TeamGuidelines.repository_id.is_(None).desc())  # Org-wide first
        .all()
    )


def db_upsert_team_guidelines(
    db: Session,
    organization_id: UUID,
    guidelines_text: str,
    feedback_count: int,
    repository_id: UUID | None = None,
) -> TeamGuidelines:
    """Create or update team guidelines for an org/repo scope.

    Args:
        db: Database session
        organization_id: Organization ID
        guidelines_text: Natural language guidelines from LLM
        feedback_count: Number of feedbacks that contributed
        repository_id: Optional repository ID for repo-specific guidelines

    Returns:
        Created or updated TeamGuidelines record
    """
    existing = db_get_team_guidelines(db, organization_id, repository_id)

    if existing:
        existing.guidelines_text = guidelines_text
        existing.feedback_count = existing.feedback_count + feedback_count
        existing.last_updated = datetime.now(UTC)
        db.commit()
        db.refresh(existing)
        return existing

    return db_create_team_guidelines(
        db=db,
        organization_id=organization_id,
        repository_id=repository_id,
        guidelines_text=guidelines_text,
        feedback_count=feedback_count,
    )


def db_update_team_guidelines(
    db: Session,
    guidelines_id: UUID,
    guidelines_text: str | None = None,
    feedback_count: int | None = None,
) -> TeamGuidelines | None:
    """Update team guidelines.

    Args:
        db: Database session
        guidelines_id: Guidelines ID
        guidelines_text: New guidelines text
        feedback_count: New feedback count

    Returns:
        Updated TeamGuidelines or None if not found
    """
    guidelines = db_get_team_guidelines_by_id(db, guidelines_id)
    if not guidelines:
        return None

    if guidelines_text is not None:
        guidelines.guidelines_text = guidelines_text
    if feedback_count is not None:
        guidelines.feedback_count = feedback_count

    guidelines.last_updated = datetime.now(UTC)

    db.commit()
    db.refresh(guidelines)
    return guidelines


def db_delete_team_guidelines(
    db: Session,
    guidelines_id: UUID,
) -> bool:
    """Delete team guidelines.

    Args:
        db: Database session
        guidelines_id: Guidelines ID

    Returns:
        True if deleted, False if not found
    """
    guidelines = db_get_team_guidelines_by_id(db, guidelines_id)
    if guidelines:
        db.delete(guidelines)
        db.commit()
        return True
    return False


def db_delete_team_guidelines_by_scope(
    db: Session,
    organization_id: UUID,
    repository_id: UUID | None = None,
) -> bool:
    """Delete team guidelines for a specific scope.

    Args:
        db: Database session
        organization_id: Organization ID
        repository_id: Optional repository ID (None = org-wide)

    Returns:
        True if deleted, False if not found
    """
    guidelines = db_get_team_guidelines(db, organization_id, repository_id)
    if guidelines:
        db.delete(guidelines)
        db.commit()
        return True
    return False
