"""SQLAlchemy database models for linked repositories."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.models.base import Base

if TYPE_CHECKING:
    from api.models.organizations import Organization
    from api.models.repositories import Repository


class LinkedRepository(Base):
    """Linked repository database model.

    Represents a repository linked to an organization or repository for context
    during code reviews. Linked repos are fetched and their AST is parsed to give
    the code reviewer access to related codebases (shared libraries, internal packages).

    Organization-level linked repos are pulled for ALL reviews in the org.
    Repository-level linked repos are added on top of org-level (purely additive).
    """

    __tablename__ = "linked_repositories"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4, index=True, name="id"
    )

    # Foreign keys - one must be set, not both
    organization_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            ondelete="CASCADE",
            name="fk_linked_repositories_organization_id_organizations",
        ),
        nullable=True,
        index=True,
        name="organization_id",
    )
    repository_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "repositories.id",
            ondelete="CASCADE",
            name="fk_linked_repositories_repository_id_repositories",
        ),
        nullable=True,
        index=True,
        name="repository_id",
    )

    # Linked repository details (external - can be any repo)
    linked_provider: Mapped[str] = mapped_column(
        String(20), nullable=False, name="linked_provider"
    )  # "github" or "gitlab"
    linked_provider_url: Mapped[str] = mapped_column(
        String(512), nullable=False, name="linked_provider_url"
    )  # e.g., https://github.com or https://gitlab.com
    linked_repo_path: Mapped[str] = mapped_column(
        String(512), nullable=False, name="linked_repo_path"
    )  # e.g., "owner/repo"
    linked_branch: Mapped[str | None] = mapped_column(
        String(255), nullable=True, name="linked_branch"
    )  # Optional specific branch (null = default branch)
    display_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, name="display_name"
    )  # For UI display

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), name="created_at"
    )

    # Unique constraints prevent duplicate links
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "linked_repo_path",
            "linked_provider_url",
            name="uq_linked_repo_org",
        ),
        UniqueConstraint(
            "repository_id",
            "linked_repo_path",
            "linked_provider_url",
            name="uq_linked_repo_repo",
        ),
    )

    # Relationships
    organization: Mapped[Organization | None] = relationship(
        "Organization", back_populates="linked_repositories"
    )
    repository: Mapped[Repository | None] = relationship(
        "Repository", back_populates="linked_repositories"
    )

    def __repr__(self) -> str:
        """String representation."""
        target = (
            f"org={self.organization_id}" if self.organization_id else f"repo={self.repository_id}"
        )
        return f"<LinkedRepository(id={self.id}, {target}, path={self.linked_repo_path})>"
