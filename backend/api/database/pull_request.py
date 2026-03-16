"""Database operations for pull requests."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from api.models.executions import Execution
from api.models.pull_requests import PullRequest


def db_create_pull_request(
    db: Session,
    organization_id: UUID,
    repository_id: UUID,
    pr_number: int,
    external_pr_id: str,
    title: str,
    author: str,
    state: str,
    head_branch: str,
    base_branch: str,
    head_sha: str,
    pr_url: str,
    created_at: datetime | None = None,
) -> PullRequest:
    """Create a new pull request.

    Args:
        db: Database session
        organization_id: Organization UUID
        repository_id: Repository UUID
        pr_number: PR/MR number (e.g., 123)
        external_pr_id: External PR ID from provider
        title: PR title
        author: PR author username
        state: PR state (open/closed/merged)
        head_branch: Source branch
        base_branch: Target branch
        head_sha: Latest commit SHA on head branch
        pr_url: Full URL to the PR
        created_at: Original PR creation date from provider (uses current time if None)

    Returns:
        Created PullRequest object
    """
    pr = PullRequest(
        organization_id=organization_id,
        repository_id=repository_id,
        pr_number=pr_number,
        external_pr_id=external_pr_id,
        title=title,
        author=author,
        state=state,
        head_branch=head_branch,
        base_branch=base_branch,
        head_sha=head_sha,
        pr_url=pr_url,
    )
    if created_at is not None:
        pr.created_at = created_at
    db.add(pr)
    db.commit()
    db.refresh(pr)
    return pr


def db_upsert_pull_request(
    db: Session,
    organization_id: UUID,
    repository_id: UUID,
    pr_number: int,
    external_pr_id: str,
    title: str,
    author: str,
    state: str,
    head_branch: str,
    base_branch: str,
    head_sha: str,
    pr_url: str,
    created_at: datetime | None = None,
) -> tuple[PullRequest, bool]:
    """Create or update a pull request.

    Looks up a PR by repository_id and pr_number. If found, updates mutable
    fields. If not found, creates a new PR.

    Args:
        db: Database session
        organization_id: Organization UUID
        repository_id: Repository UUID
        pr_number: PR/MR number (e.g., 123)
        external_pr_id: External PR ID from provider
        title: PR title
        author: PR author username
        state: PR state (open/closed/merged)
        head_branch: Source branch
        base_branch: Target branch
        head_sha: Latest commit SHA on head branch
        pr_url: Full URL to the PR
        created_at: Original PR creation date from provider (only used for new PRs)

    Returns:
        Tuple of (PullRequest object, created: bool)
        - created is True if a new PR was created, False if existing was updated
    """
    existing = db_get_pull_request_by_pr_number(db, repository_id, pr_number)

    if existing:
        # Update mutable fields (author is immutable — set only on creation)
        existing.title = title
        existing.state = state
        existing.head_branch = head_branch
        existing.base_branch = base_branch
        existing.head_sha = head_sha
        db.commit()
        db.refresh(existing)
        return existing, False

    # Create new PR
    pr = db_create_pull_request(
        db=db,
        organization_id=organization_id,
        repository_id=repository_id,
        pr_number=pr_number,
        external_pr_id=external_pr_id,
        title=title,
        author=author,
        state=state,
        head_branch=head_branch,
        base_branch=base_branch,
        head_sha=head_sha,
        pr_url=pr_url,
        created_at=created_at,
    )
    return pr, True


def db_get_pull_request_by_id(db: Session, pr_id: UUID) -> PullRequest | None:
    """Get pull request by ID.

    Args:
        db: Database session
        pr_id: Pull request UUID

    Returns:
        PullRequest object or None if not found
    """
    return db.query(PullRequest).filter(PullRequest.id == pr_id).first()


def db_get_pull_request_by_pr_number(
    db: Session, repository_id: UUID, pr_number: int
) -> PullRequest | None:
    """Get pull request by repository and PR number.

    Args:
        db: Database session
        repository_id: Repository UUID
        pr_number: PR/MR number

    Returns:
        PullRequest object or None if not found
    """
    return (
        db.query(PullRequest)
        .filter(
            PullRequest.repository_id == repository_id,
            PullRequest.pr_number == pr_number,
        )
        .first()
    )


def db_get_pull_requests_by_repository(db: Session, repository_id: UUID) -> list[PullRequest]:
    """Get all pull requests for a repository, ordered by creation date (newest first).

    Args:
        db: Database session
        repository_id: Repository UUID

    Returns:
        List of PullRequest objects
    """
    return (
        db.query(PullRequest)
        .filter(PullRequest.repository_id == repository_id)
        .order_by(PullRequest.created_at.desc())
        .all()
    )


def db_get_pull_requests_with_latest_execution(
    db: Session, repository_id: UUID, limit: int | None = None, offset: int | None = None
) -> tuple[list[tuple[PullRequest, Execution | None]], int]:
    """Get PRs with their latest execution (optimized, avoids N+1 queries).

    This function uses a subquery to find the latest execution for each PR,
    then performs a single JOIN to retrieve both PRs and their latest executions.

    Args:
        db: Database session
        repository_id: Repository UUID
        limit: Maximum number of results to return (None for all)
        offset: Number of results to skip (None for 0)

    Returns:
        Tuple of (list of (PullRequest, latest_execution_or_none) tuples, total_count)
    """
    # Subquery to get latest review execution per PR (exclude summaries)
    latest_exec_subquery = (
        db.query(
            Execution.pull_request_id,
            func.max(Execution.created_at).label("max_created"),
        )
        .filter(Execution.workflow == "review")
        .group_by(Execution.pull_request_id)
        .subquery()
    )

    # Base query for PRs with their latest execution
    base_query = (
        db.query(PullRequest, Execution)
        .outerjoin(
            latest_exec_subquery,
            PullRequest.id == latest_exec_subquery.c.pull_request_id,
        )
        .outerjoin(
            Execution,
            and_(
                Execution.pull_request_id == PullRequest.id,
                Execution.created_at == latest_exec_subquery.c.max_created,
            ),
        )
        .filter(PullRequest.repository_id == repository_id)
        .order_by(PullRequest.created_at.desc())
    )

    # Get total count before pagination
    total_count = base_query.count()

    # Apply pagination if specified
    if limit is not None:
        base_query = base_query.limit(limit)
    if offset is not None:
        base_query = base_query.offset(offset)

    results = base_query.all()

    return results, total_count


def db_update_pull_request(
    db: Session,
    pr_id: UUID,
    **kwargs,
) -> PullRequest | None:
    """Update pull request fields.

    Args:
        db: Database session
        pr_id: Pull request UUID
        **kwargs: Fields to update (e.g., title="New title", state="closed")

    Returns:
        Updated PullRequest object or None if not found
    """
    pr = db_get_pull_request_by_id(db, pr_id)
    if pr:
        for key, value in kwargs.items():
            if hasattr(pr, key):
                setattr(pr, key, value)
        db.commit()
        db.refresh(pr)
    return pr


def db_get_pull_requests_for_organizations(
    db: Session,
    organization_ids: list[UUID],
    limit: int | None = None,
    offset: int | None = None,
    state: str | None = None,
    created_after: datetime | None = None,
    search: str | None = None,
    repository_ids: list[UUID] | None = None,
    author: str | list[str] | None = None,
) -> tuple[list[tuple[PullRequest, Execution | None]], int]:
    """Get PRs with their latest execution for multiple organizations (single query).

    This function fetches all pull requests across multiple organizations in a single
    optimized query, avoiding N+1 queries by using a subquery for latest executions.

    Args:
        db: Database session
        organization_ids: List of organization UUIDs to fetch PRs for
        limit: Maximum number of results to return (None for all)
        offset: Number of results to skip (None for 0)
        state: Filter by PR state (open, closed, merged). 'open' also matches 'opened'.
        created_after: Filter PRs created after this date
        search: Search in PR title (case-insensitive)
        repository_ids: Filter by specific repository UUIDs (multi-select)
        author: Filter by PR author username(s) (exact match, single string or list)

    Returns:
        Tuple of (list of (PullRequest, latest_execution_or_none) tuples, total_count)
    """
    if not organization_ids:
        return [], 0

    # Subquery to get latest review execution per PR (exclude summaries)
    latest_exec_subquery = (
        db.query(
            Execution.pull_request_id,
            func.max(Execution.created_at).label("max_created"),
        )
        .filter(Execution.workflow == "review")
        .group_by(Execution.pull_request_id)
        .subquery()
    )

    # Base query for PRs with their latest execution
    base_query = (
        db.query(PullRequest, Execution)
        .outerjoin(
            latest_exec_subquery,
            PullRequest.id == latest_exec_subquery.c.pull_request_id,
        )
        .outerjoin(
            Execution,
            and_(
                Execution.pull_request_id == PullRequest.id,
                Execution.created_at == latest_exec_subquery.c.max_created,
            ),
        )
        .filter(PullRequest.organization_id.in_(organization_ids))
    )

    # Apply state filter (handle 'open' matching 'opened' for GitLab compatibility)
    if state:
        if state.lower() == "open":
            base_query = base_query.filter(func.lower(PullRequest.state).in_(["open", "opened"]))
        else:
            base_query = base_query.filter(func.lower(PullRequest.state) == state.lower())

    # Apply date filter
    if created_after:
        base_query = base_query.filter(PullRequest.created_at >= created_after)

    # Apply search filter (case-insensitive title search)
    if search:
        base_query = base_query.filter(func.lower(PullRequest.title).contains(search.lower()))

    # Apply repository filter (multi-select)
    if repository_ids:
        base_query = base_query.filter(PullRequest.repository_id.in_(repository_ids))

    # Apply author filter (exact match, supports multiple usernames)
    if author:
        if isinstance(author, list):
            base_query = base_query.filter(PullRequest.author.in_(author))
        else:
            base_query = base_query.filter(PullRequest.author == author)

    # Order by created_at descending
    base_query = base_query.order_by(PullRequest.created_at.desc())

    # Get total count before pagination
    total_count = base_query.count()

    # Apply pagination if specified
    if limit is not None:
        base_query = base_query.limit(limit)
    if offset is not None:
        base_query = base_query.offset(offset)

    results = base_query.all()

    return results, total_count


def db_get_executions_for_pull_request(db: Session, pr_id: UUID) -> list[Execution]:
    """Get all executions for a PR, ordered by creation date (newest first).

    Args:
        db: Database session
        pr_id: Pull request UUID

    Returns:
        List of Execution objects
    """
    return (
        db.query(Execution)
        .filter(Execution.pull_request_id == pr_id)
        .order_by(Execution.created_at.desc())
        .all()
    )


def db_get_dashboard_stats(
    db: Session,
    organization_ids: list[UUID],
) -> dict[str, Any]:
    """Get dashboard statistics for the given organizations.

    Computes stats for current 7-day period and previous 7-day period
    to enable week-over-week comparison.

    Args:
        db: Database session
        organization_ids: List of organization UUIDs to scope the stats

    Returns:
        Dict with current and previous period values:
        - active_repos / prev_active_repos
        - avg_review_time_seconds / prev_avg_review_time_seconds
        - prs_reviewed / prev_prs_reviewed
    """
    if not organization_ids:
        return {
            "active_repos": 0,
            "prev_active_repos": 0,
            "avg_review_time_seconds": None,
            "prev_avg_review_time_seconds": None,
            "prs_reviewed": 0,
            "prev_prs_reviewed": 0,
        }

    now = datetime.now(UTC)
    current_start = now - timedelta(days=7)
    prev_start = now - timedelta(days=14)

    def _query_period(start: datetime, end: datetime) -> tuple[int, float | None, int]:
        """Query stats for a single time period."""
        base_filter = and_(
            Execution.organization_id.in_(organization_ids),
            Execution.status == "completed",
            Execution.workflow == "review",
            Execution.created_at >= start,
            Execution.created_at < end,
        )

        active_repos = (
            db.query(func.count(func.distinct(Execution.repository_id)))
            .filter(base_filter)
            .scalar()
        ) or 0

        avg_time = (
            db.query(func.avg(func.extract("epoch", Execution.updated_at - Execution.created_at)))
            .filter(base_filter)
            .scalar()
        )

        prs_reviewed = (
            db.query(func.count(func.distinct(Execution.pull_request_id)))
            .filter(base_filter)
            .scalar()
        ) or 0

        return active_repos, float(avg_time) if avg_time is not None else None, prs_reviewed

    current = _query_period(current_start, now)
    previous = _query_period(prev_start, current_start)

    return {
        "active_repos": current[0],
        "prev_active_repos": previous[0],
        "avg_review_time_seconds": current[1],
        "prev_avg_review_time_seconds": previous[1],
        "prs_reviewed": current[2],
        "prev_prs_reviewed": previous[2],
    }
