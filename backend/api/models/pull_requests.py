"""SQLAlchemy database models for pull requests."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.models.base import Base

if TYPE_CHECKING:
    from api.models.executions import Execution
    from api.models.organizations import Organization
    from api.models.repositories import Repository


class PRState(StrEnum):
    """Pull request state enum."""

    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"


class PullRequest(Base):
    """Pull Request database model.

    Represents a pull request/merge request from GitHub/GitLab.
    Each PR can have multiple executions (review runs).
    """

    __tablename__ = "pull_requests"
    __mapper_args__ = {"confirm_deleted_rows": False}

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4, index=True, name="id"
    )

    # Foreign keys (tenant isolation + relationship)
    organization_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE", name="fk_pull_requests_organization_id"),
        index=True,
        name="organization_id",
    )
    repository_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE", name="fk_pull_requests_repository_id"),
        index=True,
        name="repository_id",
    )

    # PR identification
    pr_number: Mapped[int] = mapped_column(Integer, index=True, name="pr_number")
    external_pr_id: Mapped[str] = mapped_column(String(255), index=True, name="external_pr_id")

    # PR metadata
    title: Mapped[str] = mapped_column(String(512), name="title")
    author: Mapped[str] = mapped_column(String(255), name="author")
    state: Mapped[str] = mapped_column(
        String(20), default=PRState.OPEN.value, index=True, name="state"
    )

    # Branch info
    head_branch: Mapped[str] = mapped_column(String(255), name="head_branch")
    base_branch: Mapped[str] = mapped_column(String(255), name="base_branch")
    head_sha: Mapped[str] = mapped_column(
        String(40), name="head_sha"
    )  # Latest commit SHA on head branch

    # URL
    pr_url: Mapped[str] = mapped_column(String(512), name="pr_url")

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
    organization: Mapped[Organization] = relationship(
        "Organization", back_populates="pull_requests"
    )
    repository: Mapped[Repository] = relationship("Repository", back_populates="pull_requests")
    executions: Mapped[list[Execution]] = relationship(
        "Execution", back_populates="pull_request", cascade="all, delete-orphan"
    )

    # Unique constraint: one PR number per repository
    __table_args__ = (
        UniqueConstraint("repository_id", "pr_number", name="uq_pull_requests_repo_pr"),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<PullRequest(id={self.id}, repo_id={self.repository_id}, pr_number={self.pr_number})>"
        )
