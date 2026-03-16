"""SQLAlchemy database model for feedback storage.

Feedback records store raw user feedback signals (thumbs-down, replies, dismissed reviews)
that are later batch-processed into team guidelines.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.models.base import Base

if TYPE_CHECKING:
    from api.models.organizations import Organization
    from api.models.repositories import Repository


class FeedbackType(StrEnum):
    """Types of feedback signals."""

    THUMBS_DOWN = "thumbs_down"
    REPLY = "reply"
    DISMISSED = "dismissed"
    RESOLVED_WITHOUT_CHANGE = "resolved_without_change"


class Feedback(Base):
    """Raw feedback record from user interaction with a review.

    Stores unprocessed feedback signals that are batch-summarized into
    team guidelines via a periodic job.
    """

    __tablename__ = "feedbacks"
    __mapper_args__ = {"confirm_deleted_rows": False}

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4, index=True, name="id"
    )

    # Ownership - organization required, repository optional (for org-wide feedback)
    organization_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            ondelete="CASCADE",
            name="fk_feedbacks_organization_id_organizations",
        ),
        index=True,
        name="organization_id",
    )
    repository_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "repositories.id",
            ondelete="CASCADE",
            name="fk_feedbacks_repository_id_repositories",
        ),
        index=True,
        nullable=True,
        name="repository_id",
    )

    # What triggered the feedback
    feedback_type: Mapped[str] = mapped_column(
        String(50), nullable=False, name="feedback_type"
    )  # FeedbackType enum value

    # Context
    review_comment: Mapped[str] = mapped_column(
        Text, nullable=False, name="review_comment"
    )  # The AI comment that received feedback
    user_response: Mapped[str | None] = mapped_column(
        Text, nullable=True, name="user_response"
    )  # User's reply text if any
    file_path: Mapped[str | None] = mapped_column(
        String(500), nullable=True, name="file_path"
    )  # File path where comment was made

    # Metadata
    platform: Mapped[str] = mapped_column(
        String(20), nullable=False, name="platform"
    )  # "github" or "gitlab"
    processed: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, name="processed"
    )  # Marked true after batch job processes it

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), name="created_at"
    )

    # Relationships
    organization: Mapped[Organization] = relationship("Organization")
    repository: Mapped[Repository | None] = relationship("Repository")

    def __repr__(self) -> str:
        """String representation."""
        scope = f"repo:{self.repository_id}" if self.repository_id else "org-wide"
        return f"<Feedback(id={self.id}, type={self.feedback_type}, {scope}, processed={self.processed})>"
