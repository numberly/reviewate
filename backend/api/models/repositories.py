"""SQLAlchemy database models for repositories."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.models.base import Base

if TYPE_CHECKING:
    from api.models.executions import Execution
    from api.models.linked_repositories import LinkedRepository
    from api.models.organizations import Organization
    from api.models.pull_requests import PullRequest
    from api.models.users import User


class Repository(Base):
    """Repository database model.

    Stores the specific repositories that an organization has enabled for code review.
    """

    __tablename__ = "repositories"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4, index=True, name="id"
    )

    # Foreign key
    organization_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            ondelete="CASCADE",
            name="fk_repositories_organization_id_organizations",
        ),
        index=True,
        name="organization_id",
    )

    # Repository details
    external_repo_id: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, name="external_repo_id"
    )  # GitHub/GitLab repo ID (unique across all repos)
    name: Mapped[str] = mapped_column(String(512), name="name")  # e.g., 'my-project'
    web_url: Mapped[str] = mapped_column(String(512), name="web_url")  # Full URL to the repository

    # Provider information
    provider: Mapped[str] = mapped_column(
        Enum("github", "gitlab", name="provider_enum"), nullable=False, name="provider"
    )  # github or gitlab
    provider_url: Mapped[str] = mapped_column(
        String(512), nullable=False, name="provider_url"
    )  # e.g., https://github.com or https://gitlab.com or custom GitLab instance
    avatar_url: Mapped[str | None] = mapped_column(
        String(512), nullable=True, name="avatar_url"
    )  # Repository avatar URL (owner's avatar)

    # GitLab Project Access Token (encrypted with AES-256-GCM)
    # Nullable: GitHub repos use org-level app installations, GitLab repos can use project tokens
    gitlab_access_token_encrypted: Mapped[str | None] = mapped_column(
        String(512), nullable=True, name="gitlab_access_token_encrypted"
    )

    # Review settings (nullable - inherits from organization when not set)
    automatic_review_trigger: Mapped[str | None] = mapped_column(
        String(20), nullable=True, name="automatic_review_trigger"
    )  # When to auto-trigger reviews (overrides org)
    automatic_summary_trigger: Mapped[str | None] = mapped_column(
        String(20), nullable=True, name="automatic_summary_trigger"
    )  # When to auto-trigger summaries (overrides org)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), name="created_at"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        name="updated_at",
    )

    # Relationships
    organization: Mapped[Organization] = relationship("Organization", back_populates="repositories")
    pull_requests: Mapped[list[PullRequest]] = relationship(
        "PullRequest", back_populates="repository", cascade="all, delete-orphan"
    )
    executions: Mapped[list[Execution]] = relationship(
        "Execution", back_populates="repository", cascade="all, delete-orphan"
    )
    members: Mapped[list[RepositoryMembership]] = relationship(
        "RepositoryMembership",
        back_populates="repository",
        cascade="all, delete-orphan",
    )
    linked_repositories: Mapped[list[LinkedRepository]] = relationship(
        "LinkedRepository", back_populates="repository", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<Repository(id={self.id}, name={self.name})>"


class RepositoryMembership(Base):
    """Repository membership model (join table).

    Links users to individual repositories with roles.
    Used when users provide project-level access tokens instead of group tokens.
    """

    __tablename__ = "repository_memberships"
    __mapper_args__ = {"confirm_deleted_rows": False}

    # Composite primary key
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
            name="fk_repository_memberships_user_id_users",
        ),
        primary_key=True,
        name="user_id",
    )
    repository_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "repositories.id",
            ondelete="CASCADE",
            name="fk_repository_memberships_repository_id_repositories",
        ),
        primary_key=True,
        name="repository_id",
    )

    # Membership details
    role: Mapped[str] = mapped_column(String(20), default="member", name="role")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), name="created_at"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        name="updated_at",
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="repository_memberships")
    repository: Mapped[Repository] = relationship("Repository", back_populates="members")

    def __repr__(self) -> str:
        """String representation."""
        return f"<RepositoryMembership(user_id={self.user_id}, repo_id={self.repository_id}, role={self.role})>"
