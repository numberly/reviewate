"""Database operations for executions."""

import logging
from uuid import UUID

from sqlalchemy import case, desc
from sqlalchemy.orm import Session

from api.models.executions import Execution

logger = logging.getLogger(__name__)


def db_create_execution(
    db: Session,
    organization_id: UUID,
    repository_id: UUID,
    pull_request_id: UUID,
    pr_number: int,
    commit_sha: str,
    status: str,
    workflow: str = "review",
) -> Execution:
    """Create a new execution record.

    Args:
        db: Database session
        organization_id: Organization UUID
        repository_id: Repository UUID
        pull_request_id: Pull request UUID
        pr_number: PR/MR number
        commit_sha: Commit SHA being reviewed
        status: Initial execution status
        workflow: Workflow type ("review" or "summarize")

    Returns:
        Created Execution object
    """
    execution = Execution(
        organization_id=organization_id,
        repository_id=repository_id,
        pull_request_id=pull_request_id,
        pr_number=pr_number,
        commit_sha=commit_sha,
        status=status,
        workflow=workflow,
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


def db_get_execution_by_id(db: Session, execution_id: UUID) -> Execution | None:
    """Get execution by ID.

    Args:
        db: Database session
        execution_id: Execution UUID

    Returns:
        Execution object or None if not found
    """
    return db.query(Execution).filter(Execution.id == execution_id).first()


def db_update_execution_status(
    db: Session,
    execution_id: UUID,
    status: str,
    error_type: str | None = None,
    error_detail: str | None = None,
) -> Execution | None:
    """Update execution status in database.

    Args:
        db: Database session
        execution_id: Execution UUID
        status: New status value
        error_type: Optional standardized error type
        error_detail: Optional technical error detail (truncated to 2000 chars)

    Returns:
        Updated Execution object or None if not found
    """
    execution = db_get_execution_by_id(db, execution_id)
    if execution:
        execution.status = status
        if error_type is not None:
            execution.error_type = error_type
        if error_detail is not None:
            execution.error_detail = error_detail[:2000]
        db.commit()
        db.refresh(execution)

    return execution


def db_update_execution_container(
    db: Session,
    execution_id: UUID,
    container_id: str,
) -> Execution | None:
    """Update execution with container ID.

    Args:
        db: Database session
        execution_id: Execution UUID
        container_id: Container ID from Docker/K8s

    Returns:
        Updated Execution object or None if not found
    """
    execution = db_get_execution_by_id(db, execution_id)
    if execution:
        execution.container_id = container_id
        db.commit()
        db.refresh(execution)

    return execution


def db_has_active_execution(db: Session, pull_request_id: UUID, workflow: str) -> bool:
    """Check if there's an active (queued/processing) execution for a PR+workflow.

    Args:
        db: Database session
        pull_request_id: Pull request UUID
        workflow: Workflow type ("review" or "summarize")

    Returns:
        True if an active execution exists
    """
    return (
        db.query(Execution)
        .filter(
            Execution.pull_request_id == pull_request_id,
            Execution.workflow == workflow,
            Execution.status.in_(["queued", "processing"]),
        )
        .first()
        is not None
    )


def db_get_latest_executions_for_pr(db: Session, pull_request_id: UUID) -> list[Execution]:
    """Get the latest execution per workflow for a PR.

    Returns at most one execution per workflow, preferring active
    (queued/processing) over terminal (completed/failed/cancelled).

    Args:
        db: Database session
        pull_request_id: Pull request UUID

    Returns:
        List of Execution objects (at most one per workflow)
    """
    # Priority: active statuses first, then by most recent created_at
    status_priority = case(
        (Execution.status.in_(["queued", "processing"]), 0),
        else_=1,
    )

    all_executions = (
        db.query(Execution)
        .filter(Execution.pull_request_id == pull_request_id)
        .order_by(Execution.workflow, status_priority, desc(Execution.created_at))
        .all()
    )

    # Pick the first (highest priority) execution per workflow
    seen_workflows: set[str] = set()
    result: list[Execution] = []
    for exc in all_executions:
        if exc.workflow not in seen_workflows:
            seen_workflows.add(exc.workflow)
            result.append(exc)

    return result


def db_get_running_executions(
    db: Session,
    exclude_ids: set[str] | None = None,
) -> list[Execution]:
    """Get all executions that are currently running.

    Args:
        db: Database session
        exclude_ids: Optional set of execution IDs to exclude

    Returns:
        List of Execution objects with processing/queued status
    """
    query = db.query(Execution).filter(Execution.status.in_(["processing", "queued"]))
    if exclude_ids:
        query = query.filter(Execution.id.notin_(exclude_ids))
    return query.all()
