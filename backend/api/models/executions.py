"""SQLAlchemy database models for review executions."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.models.base import Base

if TYPE_CHECKING:
    from api.models.organizations import Organization
    from api.models.pull_requests import PullRequest
    from api.models.repositories import Repository


class ExecutionStatus(StrEnum):
    """Execution status values.

    Represents the state of a review job execution.
    - QUEUED: Job queued, waiting to be processed
    - PROCESSING: Job is currently running
    - COMPLETED: Job finished successfully
    - FAILED: Job failed due to error
    - CANCELLED: Job was cancelled by user or system
    """

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Execution(Base):
    """Execution database model.

    The log of every code review (workflow) that is run.
    Represents a single code review execution triggered by a PR/MR event.
    """

    __tablename__ = "executions"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4, index=True, name="id"
    )

    # Foreign keys
    organization_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            ondelete="CASCADE",
            name="fk_executions_organization_id_organizations",
        ),
        index=True,
        name="organization_id",
    )
    repository_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "repositories.id", ondelete="CASCADE", name="fk_executions_repository_id_repositories"
        ),
        index=True,
        name="repository_id",
    )
    pull_request_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "pull_requests.id",
            ondelete="CASCADE",
            name="fk_executions_pull_request_id_pull_requests",
        ),
        index=True,
        name="pull_request_id",
    )

    # Pull/Merge Request details
    pr_number: Mapped[int] = mapped_column(
        Integer, index=True, name="pr_number"
    )  # PR/MR number (e.g., 123) - kept for backward compatibility and performance
    commit_sha: Mapped[str] = mapped_column(
        String(255), name="commit_sha"
    )  # Specific commit SHA reviewed

    # Execution details
    workflow: Mapped[str] = mapped_column(
        String(20), default="review", server_default="review", name="workflow"
    )  # "review" or "summarize"
    status: Mapped[str] = mapped_column(
        String(20), default=ExecutionStatus.QUEUED.value, index=True, name="status"
    )

    # Container information (set when container is started)
    container_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, name="container_id"
    )

    # Error information (set when execution fails)
    error_type: Mapped[str | None] = mapped_column(String(50), nullable=True, name="error_type")
    error_detail: Mapped[str | None] = mapped_column(
        String(2000), nullable=True, name="error_detail"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, name="created_at"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        name="updated_at",
    )

    # Relationships
    organization: Mapped[Organization] = relationship("Organization", back_populates="executions")
    repository: Mapped[Repository] = relationship("Repository", back_populates="executions")
    pull_request: Mapped[PullRequest] = relationship("PullRequest", back_populates="executions")

    def __repr__(self) -> str:
        """String representation."""
        return f"<Execution(id={self.id}, pr_number={self.pr_number}, status={self.status})>"
